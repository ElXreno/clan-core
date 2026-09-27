import argparse
import logging

from clan_cli.completions import add_dynamic_completer, complete_machines
from clan_lib.flake import require_flake
from clan_lib.vars.prune import find_orphaned_vars, prune_vars

log = logging.getLogger(__name__)


def prune_command(args: argparse.Namespace) -> None:
    flake = require_flake(args.flake)

    orphans = find_orphaned_vars(
        args.machines or None, flake, generator_names=args.generator
    )

    print(orphans.text())
    if orphans.empty:
        return

    if args.dry_run:
        return

    if not args.yes:
        confirm = input("Delete these vars? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            log.info("Aborted.")
            return

    prune_vars(flake, orphans)
    log.info("Orphaned vars removed.")


def register_prune_parser(parser: argparse.ArgumentParser) -> None:
    machines_parser = parser.add_argument(
        "machines",
        type=str,
        help="machines to prune orphaned per-machine vars for. if empty, prune the whole clan, including shared vars",
        nargs="*",
        default=[],
    )
    add_dynamic_completer(machines_parser, complete_machines)

    parser.add_argument(
        "--generator",
        "-g",
        action="append",
        help="only prune orphaned vars of this generator. can be given multiple times",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="only list orphaned vars without removing them",
        default=False,
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="do not ask for confirmation",
        default=False,
    )
    parser.set_defaults(func=prune_command)
