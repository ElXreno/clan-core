import logging
import os
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from clan_lib.api.directory import get_clan_dir
from clan_lib.cmd import Log, RunOpts, run
from clan_lib.errors import ClanError
from clan_lib.flake.flake import Flake
from clan_lib.locked_open import locked_open
from clan_lib.machines.machines import Machine
from clan_lib.nix import nix_shell
from clan_lib.vars._types import GeneratorId, PerMachine, Shared
from clan_lib.vars.generator import Generator, get_machine_generators
from clan_lib.vars.secret_modules import sops

log = logging.getLogger(__name__)


@dataclass
class OrphanedEntry:
    generator_name: str
    var_name: str
    placement_prefix: str  # e.g. "per-machine/myhost" or "shared"
    path: Path  # absolute path to the var directory on disk
    generator_defined: bool = False


@dataclass
class StaleRecipient:
    generator: GeneratorId
    var_name: str
    machine: str

    def __str__(self) -> str:
        return f"{self.generator.rel_dir()}/{self.var_name}/machines/{self.machine}"


@dataclass
class OrphanedVars:
    entries: list[OrphanedEntry] = field(default_factory=list)
    recipients: list[StaleRecipient] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.entries and not self.recipients

    def text(self) -> str:
        if self.empty:
            return "No orphaned vars found."
        lines: list[str] = []
        if self.entries:
            lines.append("Orphaned vars:")
            lines.extend(
                f"  - {entry.placement_prefix}/{entry.generator_name}/{entry.var_name}"
                for entry in self.entries
            )
        if self.recipients:
            lines.append("Machines that no longer use a shared secret:")
            lines.extend(f"  - {recipient}" for recipient in self.recipients)
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


def _disk_machines(vars_base: Path) -> set[str]:
    per_machine_dir = vars_base / "per-machine"
    if not per_machine_dir.is_dir():
        return set()
    return {d.name for d in per_machine_dir.iterdir() if d.is_dir()}


def find_orphaned_vars(
    machine_names: Iterable[str] | None,
    flake: Flake,
    generator_names: Iterable[str] | None = None,
) -> OrphanedVars:
    """Find vars on disk that are not referenced by any generator in the current config.

    If machine_names is None, the whole clan is checked: every machine that is
    configured or still has vars on disk, and the shared vars. Otherwise only
    the per-machine vars of the given machines are checked.

    If generator_names is given, only orphans of those generators are returned.

    Machines that no longer exist in the flake config are treated as having
    zero generators, so every disk var under them is reported as orphaned
    (this is how vars for fully-removed machines get pruned).

    For shared vars, evaluates all machines to avoid removing shared vars
    still used by other machines.
    """
    vars_base = get_clan_dir(flake) / "vars"
    orphans = OrphanedVars()

    config_machines = set(flake.list_machines().keys())
    known_machines = config_machines | _disk_machines(vars_base)
    if machine_names is None:
        machine_list = sorted(known_machines)
    else:
        machine_list = list(machine_names)
        unknown = [m for m in machine_list if m not in known_machines]
        if unknown:
            msg = (
                f"Machine(s) not found in the clan or in its vars: {', '.join(unknown)}"
            )
            raise ClanError(msg)

    # --- Per-machine vars ---
    for machine_name in machine_list:
        per_machine_prefix = f"per-machine/{machine_name}"
        disk_vars = _discover_disk_vars(vars_base, per_machine_prefix)

        if not disk_vars:
            continue

        expected: set[tuple[str, str]] = set()
        defined_generators: set[str] = set()
        if machine_name in config_machines:
            generators = get_machine_generators([machine_name], flake)
            for gen in generators:
                if (
                    isinstance(gen.key.placement, PerMachine)
                    and gen.key.placement.machine == machine_name
                ):
                    defined_generators.add(gen.name)
                    for var in gen.files:
                        expected.add((gen.name, var.name))

        for gen_name, var_name in sorted(disk_vars - expected):
            var_path = vars_base / per_machine_prefix / gen_name / var_name
            orphans.entries.append(
                OrphanedEntry(
                    generator_name=gen_name,
                    var_name=var_name,
                    placement_prefix=per_machine_prefix,
                    path=var_path,
                    generator_defined=gen_name in defined_generators,
                )
            )

    # --- Shared vars ---
    shared_prefix = "shared"
    shared_disk_vars = (
        _discover_disk_vars(vars_base, shared_prefix)
        if machine_names is None
        else set()
    )

    if shared_disk_vars:
        # Evaluate ALL machines to determine which shared generators are still used
        all_generators = get_machine_generators(sorted(config_machines), flake)
        expected_shared: set[tuple[str, str]] = set()
        defined_shared: set[str] = set()
        for gen in all_generators:
            if isinstance(gen.key.placement, Shared):
                defined_shared.add(gen.name)
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
                    generator_defined=gen_name in defined_shared,
                )
            )

        orphans.recipients = _find_stale_recipients(all_generators, flake)

    if generator_names is not None:
        wanted = set(generator_names)
        orphans.entries = [e for e in orphans.entries if e.generator_name in wanted]
        orphans.recipients = [
            r for r in orphans.recipients if r.generator.name in wanted
        ]

    return orphans


def _find_stale_recipients(
    generators: Iterable[Generator], flake: Flake
) -> list[StaleRecipient]:
    """Find machines that can decrypt a shared sops secret without declaring it."""
    result: list[StaleRecipient] = []
    for gen in generators:
        if not isinstance(gen.key.placement, Shared) or not gen.machines:
            continue
        store = Machine(name=gen.machines[0], flake=flake).secret_vars_store
        if not isinstance(store, sops.SecretStore):
            continue
        for var in gen.files:
            if not var.secret or not store.exists(gen.key, var.name):
                continue
            wanted = set(var.machines) if var.deploy else set()
            result.extend(
                StaleRecipient(generator=gen.key, var_name=var.name, machine=machine)
                for machine in sorted(
                    store.machines_with_access(gen.key, var.name) - wanted
                )
            )
    return result


def _commit_removals(
    flake_dir: Path,
    removed_paths: list[Path],
    changed_paths: list[Path],
    commit_message: str,
) -> None:
    """Stage removed and changed paths and commit to git."""
    if os.environ.get("CLAN_NO_COMMIT", None):
        return
    if not removed_paths and not changed_paths:
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

    removed_strs = [str(p) for p in removed_paths]
    changed_strs = [str(p) for p in changed_paths]

    with locked_open(real_git_dir / "clan.lock", "w+"):
        if removed_strs:
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
                    *removed_strs,
                ],
            )
            run(cmd, RunOpts(log=Log.BOTH, error_msg="Failed to stage removed files"))
        if changed_strs:
            cmd = nix_shell(
                ["git"],
                ["git", "-C", str(flake_dir), "add", "--", *changed_strs],
            )
            run(cmd, RunOpts(log=Log.BOTH, error_msg="Failed to stage changed files"))

        # untracked removed paths are not valid commit pathspecs
        cmd = nix_shell(
            ["git"],
            [
                "git",
                "-C",
                str(flake_dir),
                "diff",
                "--cached",
                "--name-only",
                "-z",
                "--",
                *removed_strs,
                *changed_strs,
            ],
        )
        result = run(cmd, RunOpts(cwd=flake_dir))
        staged = [p for p in result.stdout.split("\0") if p]
        if not staged:
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
                *staged,
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
    vars_base = get_clan_dir(flake) / "vars"
    removed_paths: list[Path] = []

    for entry in orphans.entries:
        if entry.path.exists():
            shutil.rmtree(entry.path)
            removed_paths.append(entry.path)
            log.info(
                f"Removed orphaned var: {entry.placement_prefix}/{entry.generator_name}/{entry.var_name}"
            )

        if entry.generator_defined:
            continue

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
            remaining = [p for p in machine_dir.iterdir() if not p.name.startswith(".")]
            if not remaining:
                shutil.rmtree(machine_dir)
                removed_paths.append(machine_dir)
                log.info(f"Removed empty machine directory: {prefix}")

    changed_paths: list[Path] = []
    if orphans.recipients:
        store = sops.SecretStore(flake)
        for recipient in orphans.recipients:
            for path in store.revoke_machine_access(
                recipient.generator, recipient.var_name, recipient.machine
            ):
                if path.exists():
                    changed_paths.append(path)
                else:
                    removed_paths.append(path)
            log.info(f"Removed stale machine recipient: {recipient}")

    _commit_removals(
        flake.path,
        removed_paths,
        changed_paths,
        "vars: prune orphaned vars",
    )

    return removed_paths
