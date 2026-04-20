import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from clan_lib.vars.classical_keys import (
    _is_classical,
    warn_if_classical_recipients,
)

PQ = "age1pq1" + "q" * 200
CLASSICAL = "age1" + "q" * 50


def test_classical_vs_pq_classification() -> None:
    assert _is_classical(CLASSICAL)
    assert not _is_classical(PQ)
    assert not _is_classical("ssh-ed25519 AAAA")
    assert not _is_classical("")


def _write_sops(path: Path, pk: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([{"publickey": pk, "type": "age"}]))


def test_warn_fires_on_classical_sops_user(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write_sops(tmp_path / "sops" / "users" / "alice" / "key.json", CLASSICAL)
    with caplog.at_level(logging.WARNING, logger="clan_lib.vars.classical_keys"):
        warn_if_classical_recipients(tmp_path)
    assert len(caplog.records) == 1
    assert "1 classical" in caplog.records[0].message


def test_warn_silent_when_all_pq(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write_sops(tmp_path / "sops" / "users" / "alice" / "key.json", PQ)
    with caplog.at_level(logging.WARNING, logger="clan_lib.vars.classical_keys"):
        warn_if_classical_recipients(tmp_path)
    assert caplog.records == []


def test_warn_fires_on_classical_age_sidecar(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    sidecar = tmp_path / "secrets" / "clan-vars" / "g" / "s" / "s.age.recipients"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text(CLASSICAL + "\n")
    with caplog.at_level(logging.WARNING, logger="clan_lib.vars.classical_keys"):
        warn_if_classical_recipients(tmp_path)
    assert len(caplog.records) == 1


def test_warn_fires_on_classical_age_machine_pubkey_alone(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    pub = tmp_path / "secrets" / "age-keys" / "machines" / "m1" / "pub"
    pub.parent.mkdir(parents=True)
    pub.write_text(CLASSICAL + "\n")
    with caplog.at_level(logging.WARNING, logger="clan_lib.vars.classical_keys"):
        warn_if_classical_recipients(tmp_path)
    assert len(caplog.records) == 1


def test_warn_accepts_flake_object(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write_sops(tmp_path / "sops" / "users" / "alice" / "key.json", CLASSICAL)
    flake = MagicMock()
    flake.path = tmp_path
    with caplog.at_level(logging.WARNING, logger="clan_lib.vars.classical_keys"):
        warn_if_classical_recipients(flake)
    assert len(caplog.records) == 1


def test_warn_skips_none(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="clan_lib.vars.classical_keys"):
        warn_if_classical_recipients(None)
    assert caplog.records == []
