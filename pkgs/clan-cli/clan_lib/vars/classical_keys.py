import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from clan_lib.flake import Flake

log = logging.getLogger(__name__)


def _is_classical(pubkey: str) -> bool:
    pubkey = pubkey.strip()
    return pubkey.startswith("age1") and not pubkey.startswith("age1pq1")


def _count_classical_recipients(flake_path: Path) -> int:
    if not flake_path.is_dir():
        return 0
    count = 0
    for which in ("users", "machines"):
        for key_file in flake_path.glob(f"sops/{which}/*/key.json"):
            try:
                data = json.loads(key_file.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") != "age":
                    continue
                pk = entry.get("publickey")
                if isinstance(pk, str) and _is_classical(pk):
                    count += 1
    for pub_file in flake_path.glob("secrets/age-keys/machines/*/pub"):
        try:
            pk = pub_file.read_text().strip()
        except OSError:
            continue
        if _is_classical(pk):
            count += 1
    for glob_pattern in (
        "secrets/age-keys/**/*.age.recipients",
        "secrets/clan-vars/**/*.age.recipients",
    ):
        for sidecar in flake_path.glob(glob_pattern):
            try:
                lines = sidecar.read_text().splitlines()
            except OSError:
                continue
            count += sum(1 for line in lines if _is_classical(line))
    return count


def warn_if_classical_recipients(flake: Union["Flake", Path, None]) -> None:
    if flake is None:
        return
    flake_path = flake if isinstance(flake, Path) else Path(flake.path)
    try:
        count = _count_classical_recipients(flake_path)
    except Exception:  # noqa: BLE001
        log.debug("classical-recipient scan failed", exc_info=True)
        return
    if count == 0:
        return
    log.warning(
        "Detected %d classical (non-post-quantum) age recipient(s) in %s. "
        "Clan now generates post-quantum hybrid keys by default "
        "(ML-KEM-768 + X25519). See the migration guide at "
        "https://clan.lol/docs/guides/migrations/migrate-to-post-quantum-age",
        count,
        flake_path,
    )
