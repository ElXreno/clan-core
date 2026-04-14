"""Tests for post-quantum hybrid age key generation via clan-cli.

These cover the `clan.vars.settings.age.postQuantum` opt-in path introduced
for the sops and age secret backends.
"""

import pytest
from clan_cli.secrets.sops import (
    generate_private_key,
    is_post_quantum_enabled,
)


@pytest.mark.with_core
def test_is_post_quantum_enabled_returns_false_for_none_flake() -> None:
    """Without a flake, PQ must default to False for backwards compatibility."""
    assert is_post_quantum_enabled(None) is False


@pytest.mark.with_core
def test_generate_private_key_classical_returns_x25519_identity() -> None:
    """The default `generate_private_key()` still produces an X25519 identity."""
    priv, pub = generate_private_key(post_quantum=False)
    assert priv.startswith("AGE-SECRET-KEY-1"), (
        f"expected classical X25519 identity, got prefix: {priv[:20]}"
    )
    assert pub.startswith("age1"), f"expected age1 prefix, got: {pub[:20]}"
    assert not pub.startswith("age1pq1"), (
        f"unexpected post-quantum recipient in classical mode: {pub[:30]}"
    )


@pytest.mark.with_core
def test_generate_private_key_post_quantum_returns_hybrid_identity() -> None:
    """With post_quantum=True, age-keygen -pq must yield a hybrid identity.

    The hybrid format uses `AGE-SECRET-KEY-PQ-1...` for the private key and
    `age1pq1...` for the Bech32-encoded public recipient.
    """
    priv, pub = generate_private_key(post_quantum=True)
    assert priv.startswith("AGE-SECRET-KEY-PQ-1"), (
        f"expected post-quantum hybrid identity, got prefix: {priv[:25]}"
    )
    assert pub.startswith("age1pq1"), f"expected age1pq1 recipient, got: {pub[:30]}"
