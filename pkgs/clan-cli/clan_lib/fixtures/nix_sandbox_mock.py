"""Shared fixtures for mocking nix package resolution inside the test sandbox.

Inside the nix-build sandbox ``nix build nixpkgs#<pkg>`` fails with a ``chmod``
error against the read-only store — see the long note in
``clan_lib/nix/tests/test_nix_invocations.py``. These fixtures patch
:meth:`Flake.select`, :meth:`Flake.precache` and :func:`clan_lib.nix.shell.run`
so anything that goes through :func:`_resolve_package` finds a fake writable
store under ``temporary_home`` and ``nix build`` becomes a symlink-creating
no-op.

Tests opt in with::

    @pytest.mark.usefixtures("clear_nix_cache", "mock_nix_in_sandbox")

Add new entries to :data:`MOCK_PACKAGES` when a test needs a package that
isn't already covered.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from clan_lib.errors import CmdOut
from clan_lib.flake.flake import Flake
from clan_lib.nix.shell import Packages, _get_nix_shell_cache_dir

# (store_path_suffix, mainProgram, has_bin_output)
MOCK_PACKAGES: dict[str, tuple[str, str | None, bool]] = {
    "git": ("git", None, False),
    "jq": ("jq", None, True),  # jq has separate bin output
    "openssh": ("openssh", "ssh", False),
    "netcat": ("netcat", None, False),
    "dumbpipe": ("dumbpipe", None, False),
}


@pytest.fixture
def mock_nix_in_sandbox(temporary_home: Path) -> Iterator[None]:
    """Mock Flake.select and run when IN_NIX_SANDBOX is set."""
    if not os.environ.get("IN_NIX_SANDBOX"):
        yield
        return

    fake_store = temporary_home / "nix" / "store"
    fake_store.mkdir(parents=True, exist_ok=True)

    created_packages: dict[str, Path] = {}

    def get_fake_store_path(package: str, output: str = "") -> Path:
        """Get or create a fake store path for a package."""
        cache_key = f"{package}-{output}" if output else package
        if cache_key in created_packages:
            return created_packages[cache_key]

        suffix, main_program, _ = MOCK_PACKAGES.get(package, (package, None, False))
        exe_name = main_program or package

        path_suffix = f"{suffix}-{output}" if output else suffix
        store_path = fake_store / f"fakehash-{path_suffix}"
        store_path.mkdir(parents=True, exist_ok=True)

        bin_dir = store_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        exe_path = bin_dir / exe_name
        exe_path.touch()
        exe_path.chmod(0o755)

        created_packages[cache_key] = store_path
        return store_path

    real_flake_select = Flake.select

    def mock_flake_select(self: Any, selector: str) -> Any:
        """Mock Flake.select for nixpkgs package lookups; defer otherwise.

        Only selectors that look like
        ``inputs.nixpkgs.legacyPackages.<system>.<pkg>.(outPath|?meta...)``
        are answered with fake store data. Every other selector goes to the
        real implementation so tests can still read inventory / nixos config
        attributes normally.
        """
        if not selector.startswith("inputs.nixpkgs.legacyPackages."):
            return real_flake_select(self, selector)

        parts = selector.split(".")

        package = None
        for i, part in enumerate(parts):
            if part in ("outPath", "?meta"):
                package = parts[i - 1]
                break

        if package is None:
            return real_flake_select(self, selector)

        if ".outPath" in selector or selector.endswith("outPath"):
            _, _, has_bin_output = MOCK_PACKAGES.get(package, (package, None, False))
            if has_bin_output:
                return str(get_fake_store_path(package, "bin"))
            return str(get_fake_store_path(package))

        if "?meta" in selector and "?mainProgram" in selector:
            _, main_program, _ = MOCK_PACKAGES.get(package, (package, None, False))
            if main_program:
                return {"meta": {"mainProgram": main_program}}
            return {}

        if "?meta" in selector and "?outputsToInstall" in selector:
            _, _, has_bin_output = MOCK_PACKAGES.get(package, (package, None, False))
            if has_bin_output:
                return {"meta": {"outputsToInstall": ["bin", "man"]}}
            return {}

        return real_flake_select(self, selector)

    def mock_run(cmd: list[str], _options: Any = None) -> CmdOut:
        """Mock run() to create symlinks for nix build commands."""
        if len(cmd) > 0 and "nix" in cmd[0] and "build" in cmd:
            gcroot = None
            package = None

            for i, arg in enumerate(cmd):
                if arg == "--out-link" and i + 1 < len(cmd):
                    gcroot = Path(cmd[i + 1])
                elif arg.startswith("nixpkgs#"):
                    package = arg.split("#")[1]

            if gcroot and package:
                gcroot.parent.mkdir(parents=True, exist_ok=True)

                _, _, has_bin_output = MOCK_PACKAGES.get(
                    package, (package, None, False)
                )

                store_path = get_fake_store_path(package)
                if gcroot.is_symlink():
                    gcroot.unlink()
                gcroot.symlink_to(store_path)

                if has_bin_output:
                    for output in ["bin", "man"]:
                        output_gcroot = gcroot.parent / f"{gcroot.name}-{output}"
                        output_store_path = get_fake_store_path(package, output)
                        if output_gcroot.is_symlink():
                            output_gcroot.unlink()
                        output_gcroot.symlink_to(output_store_path)

                return CmdOut(
                    stdout=str(store_path),
                    stderr="",
                    cwd=Path.cwd(),
                    env=None,
                    command_list=cmd,
                    returncode=0,
                    msg=None,
                )

        msg = f"Unexpected command in sandbox mock: {cmd}"
        raise RuntimeError(msg)

    real_flake_precache = Flake.precache

    def mock_flake_precache(self: Any, selectors: list[str]) -> None:
        """Drop nixpkgs package selectors; defer the rest to the real impl.

        Package selectors are answered synthetically by ``mock_flake_select``
        so they never need to be fetched; everything else still requires a
        real nix evaluation for the test under the fixture to behave
        correctly (inventory/config reads, network exports, etc.).
        """
        real_selectors = [
            s for s in selectors if not s.startswith("inputs.nixpkgs.legacyPackages.")
        ]
        if real_selectors:
            real_flake_precache(self, real_selectors)

    with (
        patch.object(Flake, "select", mock_flake_select),
        patch.object(Flake, "precache", mock_flake_precache),
        patch("clan_lib.nix.shell.run", mock_run),
    ):
        yield


@pytest.fixture
def clear_nix_cache(temporary_home: Path) -> Iterator[None]:
    """Clear the nix shell cache before and after tests.

    Must run after temporary_home to ensure the cache uses the temp directory.
    """
    _ = temporary_home  # Ensure temporary_home runs first
    _get_nix_shell_cache_dir.cache_clear()
    Packages.static_packages = None
    yield
    _get_nix_shell_cache_dir.cache_clear()
    Packages.static_packages = None
