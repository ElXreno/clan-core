import logging
import os
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from clan_lib.cmd import Log, RunOpts, run
from clan_lib.errors import ClanError
from clan_lib.flake.flake import Flake
from clan_lib.locked_open import locked_open
from clan_lib.nix import nix_shell
from clan_lib.vars._types import PerMachine, Shared
from clan_lib.vars.generator import get_machine_generators

log = logging.getLogger(__name__)


@dataclass
class OrphanedEntry:
    generator_name: str
    var_name: str
    placement_prefix: str  # e.g. "per-machine/myhost" or "shared"
    path: Path  # absolute path to the var directory on disk


@dataclass
class OrphanedVars:
    entries: list[OrphanedEntry] = field(default_factory=list)

    def text(self) -> str:
        if not self.entries:
            return "No orphaned vars found."
        lines: list[str] = [
            f"  - {entry.placement_prefix}/{entry.generator_name}/{entry.var_name}"
            for entry in self.entries
        ]
        return "\n".join(lines)


def _discover_disk_vars(vars_base: Path, prefix: str) -> set[tuple[str, str]]:
    """Walk the filesystem to find all generator/var pairs stored on disk.

    Returns a set of (generator_name, var_name) tuples.
    """
    result: set[tuple[str, str]] = set()
    placement_dir = vars_base / prefix
    if not placement_dir.exists():
        return result

    for generator_dir in placement_dir.iterdir():
        if not generator_dir.is_dir():
            continue
        for var_dir in generator_dir.iterdir():
            if not var_dir.is_dir():
                continue
            if var_dir.name.startswith("."):
                continue  # Skip metadata like .validation-hash
            result.add((generator_dir.name, var_dir.name))

    return result


def find_orphaned_vars(
    machine_names: Iterable[str],
    flake: Flake,
) -> OrphanedVars:
    """Find vars on disk that are not referenced by any generator in the current config.

    For per-machine vars, checks each machine's generators. Machine names that
    are in the input list but no longer exist in the flake config are treated
    as having zero generators, so every disk var under them is reported as
    orphaned (this is how vars for fully-removed machines get pruned).

    For shared vars, evaluates all machines to avoid removing shared vars
    still used by other machines.
    """
    clan_dir = flake.path
    vars_base = clan_dir / "vars"
    orphans = OrphanedVars()

    machine_list = list(machine_names)
    config_machines = set(flake.list_machines().keys())

    # --- Per-machine vars ---
    for machine_name in machine_list:
        per_machine_prefix = f"per-machine/{machine_name}"
        disk_vars = _discover_disk_vars(vars_base, per_machine_prefix)

        if not disk_vars:
            continue

        if machine_name in config_machines:
            generators = get_machine_generators([machine_name], flake)
            expected: set[tuple[str, str]] = set()
            for gen in generators:
                if (
                    isinstance(gen.key.placement, PerMachine)
                    and gen.key.placement.machine == machine_name
                ):
                    for var in gen.files:
                        expected.add((gen.name, var.name))
        else:
            expected = set()

        for gen_name, var_name in sorted(disk_vars - expected):
            var_path = vars_base / per_machine_prefix / gen_name / var_name
            orphans.entries.append(
                OrphanedEntry(
                    generator_name=gen_name,
                    var_name=var_name,
                    placement_prefix=per_machine_prefix,
                    path=var_path,
                )
            )

    # --- Shared vars ---
    shared_prefix = "shared"
    shared_disk_vars = _discover_disk_vars(vars_base, shared_prefix)

    if shared_disk_vars:
        # Evaluate ALL machines to determine which shared generators are still used
        all_machine_names = list(flake.list_machines().keys())
        all_generators = get_machine_generators(all_machine_names, flake)
        expected_shared: set[tuple[str, str]] = set()
        for gen in all_generators:
            if isinstance(gen.key.placement, Shared):
                for var in gen.files:
                    expected_shared.add((gen.name, var.name))

        for gen_name, var_name in sorted(shared_disk_vars - expected_shared):
            var_path = vars_base / shared_prefix / gen_name / var_name
            orphans.entries.append(
                OrphanedEntry(
                    generator_name=gen_name,
                    var_name=var_name,
                    placement_prefix=shared_prefix,
                    path=var_path,
                )
            )

    return orphans


def _commit_removals(
    flake_dir: Path,
    removed_paths: list[Path],
    commit_message: str,
) -> None:
    """Stage removed paths and commit to git."""
    if os.environ.get("CLAN_NO_COMMIT", None):
        return
    if not removed_paths:
        return
    if not (flake_dir / ".git").exists():
        return

    dotgit = flake_dir / ".git"
    real_git_dir = flake_dir / ".git"
    if dotgit.is_file():
        actual_git_dir = dotgit.read_text().strip()
        if not actual_git_dir.startswith("gitdir: "):
            msg = f"Invalid .git file: {actual_git_dir}"
            raise ClanError(msg)
        real_git_dir = flake_dir / actual_git_dir[len("gitdir: ") :]

    path_strs = [str(p) for p in removed_paths]

    with locked_open(real_git_dir / "clan.lock", "w+"):
        # Use git rm -r --cached to stage all deletions at once
        cmd = nix_shell(
            ["git"],
            [
                "git",
                "-C",
                str(flake_dir),
                "rm",
                "-r",
                "--cached",
                "--ignore-unmatch",
                "--quiet",
                "--",
                *path_strs,
            ],
        )
        run(cmd, RunOpts(log=Log.BOTH, error_msg="Failed to stage removed files"))

        # Check if our specific paths have anything staged. Scoping the diff to
        # our own paths ensures we don't commit unrelated staged changes the
        # user might already have in the index.
        cmd = nix_shell(
            ["git"],
            [
                "git",
                "-C",
                str(flake_dir),
                "diff",
                "--cached",
                "--exit-code",
                "--quiet",
                "--",
                *path_strs,
            ],
        )
        result = run(cmd, RunOpts(check=False, cwd=flake_dir))
        if result.returncode == 0:
            return

        # --only -- <paths> restricts the commit to our pathspec, leaving any
        # other staged changes in the user's index untouched.
        cmd = nix_shell(
            ["git"],
            [
                "git",
                "-C",
                str(flake_dir),
                "commit",
                "-m",
                commit_message,
                "--no-verify",
                "--only",
                "--",
                *path_strs,
            ],
        )
        run(cmd, RunOpts(error_msg="Failed to commit removal of orphaned vars"))
        log.info("Committed removal of orphaned vars to git")


def prune_vars(
    flake: Flake,
    orphans: OrphanedVars,
) -> list[Path]:
    """Remove orphaned vars from disk.

    Returns a list of removed var directory paths.
    """
    vars_base = flake.path / "vars"
    removed_paths: list[Path] = []

    for entry in orphans.entries:
        if entry.path.exists():
            shutil.rmtree(entry.path)
            removed_paths.append(entry.path)
            log.info(
                f"Removed orphaned var: {entry.placement_prefix}/{entry.generator_name}/{entry.var_name}"
            )

        # Clean up generator dir if now empty (only real var dirs, ignore dotfiles)
        generator_dir = vars_base / entry.placement_prefix / entry.generator_name
        if generator_dir.exists():
            remaining = [
                p for p in generator_dir.iterdir() if not p.name.startswith(".")
            ]
            if not remaining:
                shutil.rmtree(generator_dir)
                removed_paths.append(generator_dir)
                log.info(
                    f"Removed empty generator directory: {entry.placement_prefix}/{entry.generator_name}"
                )

    # Clean up empty per-machine/<machine> dirs left behind after removing all
    # generators under them (e.g. when a machine itself is no longer in config).
    machine_prefixes = {
        entry.placement_prefix
        for entry in orphans.entries
        if entry.placement_prefix.startswith("per-machine/")
    }
    for prefix in sorted(machine_prefixes):
        machine_dir = vars_base / prefix
        if machine_dir.exists():
            remaining = [
                p for p in machine_dir.iterdir() if not p.name.startswith(".")
            ]
            if not remaining:
                shutil.rmtree(machine_dir)
                removed_paths.append(machine_dir)
                log.info(f"Removed empty machine directory: {prefix}")

    _commit_removals(
        flake.path,
        removed_paths,
        "Remove orphaned vars",
    )

    return removed_paths
