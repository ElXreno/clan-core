from clan_cli.secrets.sops import generate_private_key


def test_generate_private_key_returns_hybrid_identity() -> None:
    priv, pub = generate_private_key()
    assert priv.startswith("AGE-SECRET-KEY-PQ-1")
    assert pub.startswith("age1pq1")
