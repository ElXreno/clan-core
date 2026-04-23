"""Test to verify nix command caching behavior.

This test verifies that _resolve_package (which uses Flake.select and nix_add_to_gcroots)
is properly cached using symlinks as GC roots, so repeated nix_shell calls for the
same package only trigger one actual nix evaluation.

Note: I really tried to make nix build work inside the sandbox, however in combination with
--inputs-from pointing to a custom directory of a custom build flake for remote inputs and
--store to a custom dir. Nix build would fail with an 'chmod' error. Instead we use the
``mock_nix_in_sandbox`` fixture (see :mod:`clan_cli.tests.nix_sandbox_mock`), which patches
package resolution to point at a fake writable store.
"""

import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import clan_lib.nix.shell as shell_module
from clan_lib.dirs import runtime_deps_flake
from clan_lib.nix.shell import (
    ResolvedPackage,
    _create_gcroot,
    _get_nix_shell_cache_dir,
    _resolve_package,
    nix_shell,
)

log = logging.getLogger(__name__)


@pytest.mark.usefixtures("clear_nix_cache", "mock_nix_in_sandbox")
def test_resolve_package_returns_resolved_package() -> None:
    """Test that _resolve_package returns a ResolvedPackage with correct data."""
    nixpkgs_path = runtime_deps_flake().resolve()
    result = _resolve_package(nixpkgs_path, "git")

    assert result is not None
    assert isinstance(result, ResolvedPackage)
    assert result.store_path.exists()
    assert result.exe_name == "git"


@pytest.mark.usefixtures("clear_nix_cache", "mock_nix_in_sandbox")
def test_resolve_package_returns_exe_name() -> None:
    """Test that _resolve_package returns the correct executable name."""
    nixpkgs_path = runtime_deps_flake().resolve()
    result = _resolve_package(nixpkgs_path, "git")

    assert result is not None
    assert result.exe_name == "git"


@pytest.mark.usefixtures("clear_nix_cache", "mock_nix_in_sandbox")
def test_resolve_package_multi_output() -> None:
    """Test that _resolve_package handles packages with multiple outputs."""
    nixpkgs_path = runtime_deps_flake().resolve()
    result = _resolve_package(nixpkgs_path, "jq")

    assert result is not None
    assert result.exe_name == "jq"

    # Check that symlink was created (jq has bin output)
    cache_dir = _get_nix_shell_cache_dir(nixpkgs_path)
    cache_link = cache_dir / "jq-bin"
    assert cache_link.is_symlink()
    assert cache_link.resolve() == result.store_path


@pytest.mark.usefixtures("clear_nix_cache", "mock_nix_in_sandbox")
def test_resolve_package_creates_gcroot_symlink() -> None:
    """Test that _resolve_package creates a GC root symlink."""
    nixpkgs_path = runtime_deps_flake().resolve()
    result = _resolve_package(nixpkgs_path, "git")

    assert result is not None

    # Check that symlink was created in cache dir
    cache_dir = _get_nix_shell_cache_dir(nixpkgs_path)
    cache_link = cache_dir / "git"
    assert cache_link.is_symlink()
    # Symlink should point to a valid nix store path
    assert cache_link.resolve().exists()
    # In sandbox mode, we use a fake store path; outside sandbox, check real /nix/store/
    if not os.environ.get("IN_NIX_SANDBOX"):
        assert str(cache_link.resolve()).startswith("/nix/store/")


@pytest.mark.usefixtures("clear_nix_cache", "mock_nix_in_sandbox")
def test_resolve_package_uses_main_program_from_meta() -> None:
    """Test that _resolve_package uses mainProgram from meta when available."""
    nixpkgs_path = runtime_deps_flake().resolve()
    # openssh has mainProgram = "ssh"
    result = _resolve_package(nixpkgs_path, "openssh")

    assert result is not None
    assert result.exe_name == "ssh"  # Uses mainProgram, not package name

    # Verify the binary exists at the expected location
    binary_path = result.store_path / "bin" / result.exe_name
    assert binary_path.exists(), f"Binary should exist at {binary_path}"


@pytest.mark.usefixtures("clear_nix_cache", "mock_nix_in_sandbox")
def test_resolve_package_detects_broken_symlink() -> None:
    """Test that broken symlinks are detected and re-resolved."""
    nixpkgs_path = runtime_deps_flake().resolve()

    # First resolution
    result1 = _resolve_package(nixpkgs_path, "git")
    assert result1 is not None

    # Simulate garbage collection by replacing with a broken symlink
    cache_dir = _get_nix_shell_cache_dir(nixpkgs_path)
    cache_link = cache_dir / "git"
    cache_link.unlink()
    cache_link.symlink_to("/nix/store/nonexistent-path")

    # Next resolution should detect the broken symlink and re-resolve
    result2 = _resolve_package(nixpkgs_path, "git")
    assert result2 is not None
    # Should have a valid store path again
    assert result2.store_path.exists()
    assert result2.exe_name == "git"


@pytest.mark.usefixtures("clear_nix_cache")
def test_cache_isolation_by_nixpkgs_path() -> None:
    """Test that different nixpkgs paths use different cache directories."""
    # Get cache dirs for different nixpkgs paths
    cache_dir1 = _get_nix_shell_cache_dir(Path("/nix/store/path1-nixpkgs"))
    cache_dir2 = _get_nix_shell_cache_dir(Path("/nix/store/path2-nixpkgs"))

    assert cache_dir1 != cache_dir2, "Different nixpkgs should use different cache dirs"
    assert cache_dir1.parent == cache_dir2.parent, "Cache dirs should be siblings"


@pytest.mark.usefixtures("clear_nix_cache", "mock_nix_in_sandbox")
def test_nix_shell_uses_resolved_paths() -> None:
    """Test that nix_shell uses resolved package paths to modify PATH."""
    with patch.dict("os.environ", {"IN_NIX_SANDBOX": "", "CLAN_PROVIDED_PACKAGES": ""}):
        result = nix_shell(["netcat"], ["nc", "test"])

    # Should return env command with PATH modification
    assert result[0] == "env"
    assert result[1].startswith("PATH=")
    assert "/bin" in result[1]


def test_nix_shell_skips_provided_packages() -> None:
    """Test that nix_shell skips packages already provided."""
    with (
        patch("clan_lib.nix.shell.Packages.is_provided", return_value=True),
        patch("clan_lib.nix.shell.Packages.ensure_allowed"),
        patch.dict("os.environ", {"IN_NIX_SANDBOX": ""}),
    ):
        result = nix_shell(["git"], ["echo", "test"])

        # Should return command unchanged (no env wrapper)
        assert result == ["echo", "test"]


def test_nix_shell_skips_in_sandbox() -> None:
    """Test that nix_shell returns command unchanged in nix sandbox."""
    with (
        patch("clan_lib.nix.shell.Packages.ensure_allowed"),
        patch.dict("os.environ", {"IN_NIX_SANDBOX": "1"}),
    ):
        result = nix_shell(["git"], ["echo", "test"])

        # Should return command unchanged
        assert result == ["echo", "test"]


@pytest.mark.usefixtures("clear_nix_cache", "mock_nix_in_sandbox")
def test_resolve_single_package_cache_hit_skips_gcroot_creation() -> None:
    """Test that cached symlinks prevent _create_gcroot from being called again.

    Uses sops because it has a single "out" symlink output called "sops"
    """
    nixpkgs_path = runtime_deps_flake().resolve()

    # Track _create_gcroot calls
    gcroot_call_count = [0]
    original_create_gcroot = _create_gcroot

    def counting_create_gcroot(
        package: str, nixpkgs_path: Path, gcroot_path: Path
    ) -> None:
        gcroot_call_count[0] += 1
        return original_create_gcroot(package, nixpkgs_path, gcroot_path)

    with patch.object(shell_module, "_create_gcroot", counting_create_gcroot):
        # First resolution - should call _create_gcroot
        result1 = _resolve_package(nixpkgs_path, "sops")
        assert result1 is not None
        assert gcroot_call_count[0] == 1, "First call should trigger _create_gcroot"

        # Verify symlinks were created (jq has bin and man outputs)
        cache_dir = _get_nix_shell_cache_dir(nixpkgs_path)
        cache_link_bin = cache_dir / "sops"
        assert cache_link_bin.is_symlink(), (
            "GC root symlink for out output should exist"
        )

        # Second resolution - should use cache, NOT call _create_gcroot
        result2 = _resolve_package(nixpkgs_path, "sops")
        assert result2 is not None
        assert gcroot_call_count[0] == 1, (
            "Second call should use cache, not _create_gcroot"
        )

        # Results should be equivalent
        assert result1.store_path == result2.store_path
        assert result1.exe_name == result2.exe_name


@pytest.mark.usefixtures("clear_nix_cache", "mock_nix_in_sandbox")
def test_resolve_multi_package_cache_hit_skips_gcroot_creation() -> None:
    """Test that cached symlinks prevent _create_gcroot from being called again.

    Uses jq because it has multiple outputs (bin, man), verifying that the
    multi-output cache logic works correctly.
    """
    nixpkgs_path = runtime_deps_flake().resolve()

    # Track _create_gcroot calls
    gcroot_call_count = [0]
    original_create_gcroot = _create_gcroot

    def counting_create_gcroot(
        package: str, nixpkgs_path: Path, gcroot_path: Path
    ) -> None:
        gcroot_call_count[0] += 1
        return original_create_gcroot(package, nixpkgs_path, gcroot_path)

    with patch.object(shell_module, "_create_gcroot", counting_create_gcroot):
        # First resolution - should call _create_gcroot
        result1 = _resolve_package(nixpkgs_path, "jq")
        assert result1 is not None
        assert gcroot_call_count[0] == 1, "First call should trigger _create_gcroot"

        # Verify symlinks were created (jq has bin and man outputs)
        cache_dir = _get_nix_shell_cache_dir(nixpkgs_path)
        cache_link_bin = cache_dir / "jq-bin"
        assert cache_link_bin.is_symlink(), (
            "GC root symlink for bin output should exist"
        )

        # Second resolution - should use cache, NOT call _create_gcroot
        result2 = _resolve_package(nixpkgs_path, "jq")
        assert result2 is not None
        assert gcroot_call_count[0] == 1, (
            "Second call should use cache, not _create_gcroot"
        )

        # Results should be equivalent
        assert result1.store_path == result2.store_path
        assert result1.exe_name == result2.exe_name
