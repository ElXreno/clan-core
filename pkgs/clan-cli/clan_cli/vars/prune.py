import argparse
import logging

from clan_cli.completions import add_dynamic_completer, complete_machines
from clan_lib.flake import require_flake
from clan_lib.machines.list import list_full_machines
from clan_lib.vars.prune import find_orphaned_vars, prune_vars

log = logging.getLogger(__name__)


def prune_command(args: argparse.Namespace) -> None:
    flake = require_flake(args.flake)

    if args.machines:
        machine_names = args.machines
    else:
        machine_names = list(list_full_machines(flake).keys())

    orphans = find_orphaned_vars(machine_names, flake)

    if not orphans.entries:
        log.info("No orphaned vars found.")
        return

    log.info(f"Found orphaned vars:\n{orphans.text()}")

    if args.dry_run:
        return

    prune_vars(flake, orphans)
    log.info("Orphaned vars removed.")


def register_prune_parser(parser: argparse.ArgumentParser) -> None:
    machines_parser = parser.add_argument(
        "machines",
        type=str,
        help="machines to prune orphaned vars for. if empty, prune for all machines",
        nargs="*",
        default=[],
    )
    add_dynamic_completer(machines_parser, complete_machines)

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="only list orphaned vars without removing them",
        default=False,
    )
    parser.set_defaults(func=prune_command)
