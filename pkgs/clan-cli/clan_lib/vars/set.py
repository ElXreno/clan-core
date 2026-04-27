import logging
import sys

from clan_cli.vars.get import get_machine_var

from clan_lib.flake import Flake
from clan_lib.git import commit_files
from clan_lib.machines.machines import Machine
from clan_lib.vars.generator import Var, get_machine_generators
from clan_lib.vars.prompt import PromptType, ask

log = logging.getLogger(__name__)


def _resolve_shared_var(machine: Machine, gen_name: str, var: Var) -> Var:
    """Re-evaluate with all machines so shared generators have the full machine list.

    For shared generators, a single-machine evaluation only sees one machine.
    This re-evaluates all machines so var.machines (and thus StoreRequest)
    reflects the complete declared state from Nix.
    """
    all_machine_names = list(machine.flake.list_machines().keys())
    generators = get_machine_generators(all_machine_names, machine.flake)
    for gen in generators:
        if gen.name != gen_name or not gen.share:
            continue
        for v in gen.files:
            if v.name == var.name:
                if v.secret:
                    v.store(machine.secret_vars_store)
                else:
                    v.store(machine.public_vars_store)
                v.generator(gen)
                return v
    return var


def set_var(machine: str | Machine, var: str | Var, value: bytes, flake: Flake) -> None:
    if isinstance(machine, str):
        _machine = Machine(name=machine, flake=flake)
    else:
        _machine = machine
    _var = get_machine_var(_machine, var) if isinstance(var, str) else var

    # TODO: Resolve the generator first, so we don't need to get it from private variable
    gen = _var._generator  # noqa: SLF001
    if gen is not None and gen.share:
        _var = _resolve_shared_var(_machine, gen.name, _var)

    paths = _var.set(value, _machine.name)
    if paths:
        commit_files(
            paths,
            _machine.flake_dir,
            f"vars: update {_var.id} for machine {_machine.name}",
        )


def set_via_stdin(machine_name: str, var_id: str, flake: Flake) -> None:
    machine = Machine(name=machine_name, flake=flake)
    var = get_machine_var(machine, var_id)
    if sys.stdin.isatty():
        new_value = ask(
            var.id,
            PromptType.MULTILINE_HIDDEN,
            None,
            [machine_name],
        ).encode("utf-8")
    else:
        new_value = sys.stdin.buffer.read()

    set_var(machine, var, new_value, flake)
