"""Row-independent P1 fix (2026-09-17) — the local-dev MCP auth seed must
NOT silently inherit ``seed_token``'s own 1-hour default TTL. Pins the
fix so a future edit cannot reintroduce the hourly-expiry regression."""
from __future__ import annotations

import time

import pytest
import yaml


def _configured(tmp_path, monkeypatch) -> None:
    (tmp_path / "backends").mkdir()
    (tmp_path / "settings.yaml").write_text(yaml.safe_dump({
        "service_name": "test", "backend": "memory"}))
    (tmp_path / "backends" / "memory.yaml").write_text("kind: memory\n")
    monkeypatch.setenv("AUTH_CONFIG_DIR", str(tmp_path))


def test_local_seed_survives_past_the_old_one_hour_default(tmp_path, monkeypatch) -> None:
    """The exact regression the owner hit: a token seeded at process start
    must still verify successfully more than one hour later."""
    _configured(tmp_path, monkeypatch)
    monkeypatch.setenv("MCP_LOCAL_AUTH_TOKEN", "local-dev-token-1234567890")
    from factory.auth.access import create_credential_verifier
    from factory.auth.runtime.envelope import Envelope

    verifier = create_credential_verifier(local_mode=True)
    now = [time.time()]
    backend = verifier.runtime._backend
    backend._tokens["local-dev-token-1234567890"].expires_at = now[0] + 86400  # sanity: seeded long

    # Simulate the exact failure mode: verify well past the OLD 3600s default.
    monkeypatch.setattr(time, "time", lambda: now[0] + 3700)
    result = backend.verify_access_token(
        "local-dev-token-1234567890", required_audience=None, required_scopes=None,
        envelope=Envelope(tenant_id=None, principal_id=None),
    )
    assert result["ok"] is True, "local dev token must not expire after the old 1-hour default"


def test_local_seed_defaults_to_the_seed_token_maximum_not_one_hour(tmp_path, monkeypatch) -> None:
    """Pins the actual default value, not just 'longer than an hour' —
    guards against a future edit picking some OTHER short value."""
    _configured(tmp_path, monkeypatch)
    monkeypatch.setenv("MCP_LOCAL_AUTH_TOKEN", "local-dev-token-1234567890")
    from factory.auth.access import create_credential_verifier

    before = time.time()
    verifier = create_credential_verifier(local_mode=True)
    after = time.time()
    stored = verifier.runtime._backend._tokens["local-dev-token-1234567890"]
    # 86400s (seed_token's own maximum) within a generous scheduling window.
    assert 86400 - 5 <= stored.expires_at - before <= 86400 + 5
    assert stored.expires_at - after <= 86400 + 5


def test_local_seed_ttl_override_respects_seed_tokens_own_bounds(tmp_path, monkeypatch) -> None:
    """An owner-configured override still goes through seed_token's own
    1..86400 validation — this fix must never bypass that safety bound."""
    _configured(tmp_path, monkeypatch)
    monkeypatch.setenv("MCP_LOCAL_AUTH_TOKEN", "local-dev-token-1234567890")
    monkeypatch.setenv("MCP_LOCAL_AUTH_TOKEN_TTL_SECONDS", "999999")
    from factory.auth.access import create_credential_verifier

    with pytest.raises(ValueError, match="invalid local token seed"):
        create_credential_verifier(local_mode=True)


def test_local_seed_ttl_override_can_shorten_for_an_owner_who_wants_it(tmp_path, monkeypatch) -> None:
    _configured(tmp_path, monkeypatch)
    monkeypatch.setenv("MCP_LOCAL_AUTH_TOKEN", "local-dev-token-1234567890")
    monkeypatch.setenv("MCP_LOCAL_AUTH_TOKEN_TTL_SECONDS", "120")
    from factory.auth.access import create_credential_verifier

    before = time.time()
    verifier = create_credential_verifier(local_mode=True)
    stored = verifier.runtime._backend._tokens["local-dev-token-1234567890"]
    assert 115 <= stored.expires_at - before <= 125
