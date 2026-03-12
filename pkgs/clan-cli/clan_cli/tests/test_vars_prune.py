import subprocess as sp

import pytest
from clan_cli.tests.fixtures_flakes import ClanFlake, create_test_machine_config
from clan_cli.tests.helpers import cli
from clan_lib.flake import Flake
from clan_lib.vars._types import GeneratorId, PerMachine, Shared
from clan_lib.vars.generator import Generator
from clan_lib.vars.prune import find_orphaned_vars, prune_vars
from clan_lib.vars.public_modules import in_repo


@pytest.mark.broken_on_darwin
@pytest.mark.with_core
def test_prune_no_orphans(
    monkeypatch: pytest.MonkeyPatch,
    flake_with_sops: ClanFlake,
) -> None:
    """Prune does nothing when all vars on disk match generators in config."""
    flake = flake_with_sops

    config = flake.machines["my_machine"] = create_test_machine_config()
    gen = config["clan"]["core"]["vars"]["generators"]["my_generator"]
    gen["files"]["my_value"]["secret"] = False
    gen["script"] = 'echo -n hello > "$out"/my_value'

    flake.refresh()
    monkeypatch.chdir(flake.path)

    cli.run(["vars", "generate", "--flake", str(flake.path), "my_machine"])

    # Verify var exists
    flake_obj = Flake(str(flake.path))
    store = in_repo.VarsStore(flake=flake_obj)
    generator = Generator(
        key=GeneratorId(name="my_generator", placement=PerMachine(machine="my_machine")),
        _flake=flake_obj,
    )
    assert store.exists(generator.key, "my_value")

    # Prune should find nothing
    orphans = find_orphaned_vars(["my_machine"], flake_obj)
    assert len(orphans.entries) == 0


@pytest.mark.broken_on_darwin
@pytest.mark.with_core
def test_prune_removes_orphaned_per_machine_vars(
    monkeypatch: pytest.MonkeyPatch,
    flake_with_sops: ClanFlake,
) -> None:
    """Prune removes per-machine vars whose generator was removed from config."""
    flake = flake_with_sops

    # Set up two generators
    config = flake.machines["my_machine"] = create_test_machine_config()
    gen_keep = config["clan"]["core"]["vars"]["generators"]["gen_keep"]
    gen_keep["files"]["kept_value"]["secret"] = False
    gen_keep["script"] = 'echo -n keep > "$out"/kept_value'

    gen_remove = config["clan"]["core"]["vars"]["generators"]["gen_remove"]
    gen_remove["files"]["removed_value"]["secret"] = False
    gen_remove["script"] = 'echo -n remove > "$out"/removed_value'

    flake.refresh()
    monkeypatch.chdir(flake.path)

    cli.run(["vars", "generate", "--flake", str(flake.path), "my_machine"])

    flake_obj = Flake(str(flake.path))
    store = in_repo.VarsStore(flake=flake_obj)
    assert store.exists(
        GeneratorId(name="gen_keep", placement=PerMachine(machine="my_machine")),
        "kept_value",
    )
    assert store.exists(
        GeneratorId(name="gen_remove", placement=PerMachine(machine="my_machine")),
        "removed_value",
    )

    # Remove gen_remove from config
    config = flake.machines["my_machine"] = create_test_machine_config()
    gen_keep = config["clan"]["core"]["vars"]["generators"]["gen_keep"]
    gen_keep["files"]["kept_value"]["secret"] = False
    gen_keep["script"] = 'echo -n keep > "$out"/kept_value'
    # gen_remove is intentionally NOT added back

    flake.refresh()

    # Find orphans
    flake_obj = Flake(str(flake.path))
    orphans = find_orphaned_vars(["my_machine"], flake_obj)
    assert len(orphans.entries) == 1
    assert orphans.entries[0].generator_name == "gen_remove"
    assert orphans.entries[0].var_name == "removed_value"

    # Prune
    prune_vars(flake_obj, orphans)

    # Verify removed
    store = in_repo.VarsStore(flake=flake_obj)
    assert not store.exists(
        GeneratorId(name="gen_remove", placement=PerMachine(machine="my_machine")),
        "removed_value",
    )
    # Verify kept var is untouched
    assert store.exists(
        GeneratorId(name="gen_keep", placement=PerMachine(machine="my_machine")),
        "kept_value",
    )

    # Verify git is clean after prune
    result = sp.run(
        ["git", "status", "--porcelain"],
        cwd=flake.path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == ""


@pytest.mark.broken_on_darwin
@pytest.mark.with_core
def test_prune_shared_vars_only_when_unused_by_all_machines(
    monkeypatch: pytest.MonkeyPatch,
    flake_with_sops: ClanFlake,
) -> None:
    """Shared vars are only pruned if no machine references the generator."""
    flake = flake_with_sops

    # Machine 1 uses shared_gen
    config1 = flake.machines["machine1"] = create_test_machine_config()
    shared_gen = config1["clan"]["core"]["vars"]["generators"]["shared_gen"]
    shared_gen["share"] = True
    shared_gen["files"]["shared_val"]["secret"] = False
    shared_gen["script"] = 'echo -n shared > "$out"/shared_val'

    # Machine 2 also uses shared_gen
    config2 = flake.machines["machine2"] = create_test_machine_config()
    shared_gen2 = config2["clan"]["core"]["vars"]["generators"]["shared_gen"]
    shared_gen2["share"] = True
    shared_gen2["files"]["shared_val"]["secret"] = False
    shared_gen2["script"] = 'echo -n shared > "$out"/shared_val'

    flake.refresh()
    monkeypatch.chdir(flake.path)

    cli.run(["vars", "generate", "--flake", str(flake.path)])

    flake_obj = Flake(str(flake.path))
    store = in_repo.VarsStore(flake=flake_obj)
    assert store.exists(GeneratorId(name="shared_gen", placement=Shared()), "shared_val")

    # Remove shared_gen from machine1 only — machine2 still uses it
    config1 = flake.machines["machine1"] = create_test_machine_config()
    # No shared_gen for machine1

    flake.refresh()

    flake_obj = Flake(str(flake.path))
    orphans = find_orphaned_vars(["machine1"], flake_obj)
    # shared_gen should NOT be orphaned because machine2 still uses it
    shared_orphans = [e for e in orphans.entries if e.placement_prefix == "shared"]
    assert len(shared_orphans) == 0


@pytest.mark.broken_on_darwin
@pytest.mark.with_core
def test_prune_shared_vars_when_no_machine_uses_them(
    monkeypatch: pytest.MonkeyPatch,
    flake_with_sops: ClanFlake,
) -> None:
    """Shared vars are pruned when no machine references the generator anymore."""
    flake = flake_with_sops

    config = flake.machines["my_machine"] = create_test_machine_config()
    shared_gen = config["clan"]["core"]["vars"]["generators"]["orphan_shared"]
    shared_gen["share"] = True
    shared_gen["files"]["val"]["secret"] = False
    shared_gen["script"] = 'echo -n data > "$out"/val'

    flake.refresh()
    monkeypatch.chdir(flake.path)

    cli.run(["vars", "generate", "--flake", str(flake.path), "my_machine"])

    flake_obj = Flake(str(flake.path))
    store = in_repo.VarsStore(flake=flake_obj)
    assert store.exists(GeneratorId(name="orphan_shared", placement=Shared()), "val")

    # Remove the shared generator from config
    config = flake.machines["my_machine"] = create_test_machine_config()
    # orphan_shared is intentionally NOT added back

    flake.refresh()

    flake_obj = Flake(str(flake.path))
    orphans = find_orphaned_vars(["my_machine"], flake_obj)
    shared_orphans = [e for e in orphans.entries if e.placement_prefix == "shared"]
    assert len(shared_orphans) == 1
    assert shared_orphans[0].generator_name == "orphan_shared"
    assert shared_orphans[0].var_name == "val"

    prune_vars(flake_obj, orphans)

    store = in_repo.VarsStore(flake=flake_obj)
    assert not store.exists(GeneratorId(name="orphan_shared", placement=Shared()), "val")


@pytest.mark.broken_on_darwin
@pytest.mark.with_core
def test_prune_dry_run_does_not_remove(
    monkeypatch: pytest.MonkeyPatch,
    flake_with_sops: ClanFlake,
) -> None:
    """--dry-run lists orphaned vars without removing them."""
    flake = flake_with_sops

    config = flake.machines["my_machine"] = create_test_machine_config()
    gen = config["clan"]["core"]["vars"]["generators"]["temp_gen"]
    gen["files"]["temp_val"]["secret"] = False
    gen["script"] = 'echo -n temp > "$out"/temp_val'

    flake.refresh()
    monkeypatch.chdir(flake.path)

    cli.run(["vars", "generate", "--flake", str(flake.path), "my_machine"])

    # Remove generator from config
    config = flake.machines["my_machine"] = create_test_machine_config()
    flake.refresh()

    # Run prune with --dry-run via CLI
    cli.run(["vars", "prune", "--flake", str(flake.path), "my_machine", "--dry-run"])

    # Var should still exist
    flake_obj = Flake(str(flake.path))
    store = in_repo.VarsStore(flake=flake_obj)
    assert store.exists(
        GeneratorId(name="temp_gen", placement=PerMachine(machine="my_machine")),
        "temp_val",
    )


@pytest.mark.broken_on_darwin
@pytest.mark.with_core
def test_prune_via_cli(
    monkeypatch: pytest.MonkeyPatch,
    flake_with_sops: ClanFlake,
) -> None:
    """Test the full CLI flow: generate, remove generator, prune."""
    flake = flake_with_sops

    config = flake.machines["my_machine"] = create_test_machine_config()
    gen = config["clan"]["core"]["vars"]["generators"]["cli_gen"]
    gen["files"]["cli_val"]["secret"] = False
    gen["script"] = 'echo -n cli > "$out"/cli_val'

    flake.refresh()
    monkeypatch.chdir(flake.path)

    cli.run(["vars", "generate", "--flake", str(flake.path), "my_machine"])

    # Remove generator from config
    config = flake.machines["my_machine"] = create_test_machine_config()
    flake.refresh()

    # Run prune via CLI (no --dry-run)
    cli.run(["vars", "prune", "--flake", str(flake.path), "my_machine"])

    # Var should be removed
    flake_obj = Flake(str(flake.path))
    store = in_repo.VarsStore(flake=flake_obj)
    assert not store.exists(
        GeneratorId(name="cli_gen", placement=PerMachine(machine="my_machine")),
        "cli_val",
    )

    # Generator directory should be cleaned up
    gen_dir = flake.path / "vars" / "per-machine" / "my_machine" / "cli_gen"
    assert not gen_dir.exists()


@pytest.mark.broken_on_darwin
@pytest.mark.with_core
def test_prune_all_machines(
    monkeypatch: pytest.MonkeyPatch,
    flake_with_sops: ClanFlake,
) -> None:
    """Prune with no machine argument prunes all machines."""
    flake = flake_with_sops

    # Create two machines with generators
    config1 = flake.machines["machine_a"] = create_test_machine_config()
    gen1 = config1["clan"]["core"]["vars"]["generators"]["gen_a"]
    gen1["files"]["val_a"]["secret"] = False
    gen1["script"] = 'echo -n a > "$out"/val_a'

    config2 = flake.machines["machine_b"] = create_test_machine_config()
    gen2 = config2["clan"]["core"]["vars"]["generators"]["gen_b"]
    gen2["files"]["val_b"]["secret"] = False
    gen2["script"] = 'echo -n b > "$out"/val_b'

    flake.refresh()
    monkeypatch.chdir(flake.path)

    cli.run(["vars", "generate", "--flake", str(flake.path)])

    # Remove generators from both machines
    flake.machines["machine_a"] = create_test_machine_config()
    flake.machines["machine_b"] = create_test_machine_config()
    flake.refresh()

    # Prune all machines (no machine arg)
    cli.run(["vars", "prune", "--flake", str(flake.path)])

    flake_obj = Flake(str(flake.path))
    store = in_repo.VarsStore(flake=flake_obj)
    assert not store.exists(
        GeneratorId(name="gen_a", placement=PerMachine(machine="machine_a")),
        "val_a",
    )
    assert not store.exists(
        GeneratorId(name="gen_b", placement=PerMachine(machine="machine_b")),
        "val_b",
    )
