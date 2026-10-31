"""bd-5swj adversarial properties for ``aws_creds.force_refresh``.

Companion to ``test_aws_creds_properties.py`` (bd-4kq2 P-CR1..P-CR5);
split out per the brick's sibling ``_props`` convention so neither file
exceeds the 200 LOC tenet. Verdicts: meta-architect ``82cb1367``,
strands-expert ``8e65dbf0``.

P-CR9  ``force_refresh`` drops the singleton, the next factory call
       returns a NEW ``boto3.Session`` whose deferred refresher is a
       NEW ``DeferredRefreshableCredentials`` instance loading fresh
       on-disk values. Idempotent when ``_SESSION is None``.
P-CR10 ``force_refresh`` is safe under concurrent calls (no deadlock,
       no raise) and the post-refresh ``get_refreshable_session``
       singleton invariant from P-CR5 still holds in race conditions.

Driver pattern mirrors P-CR4/P-CR5 — ``_setup_factory`` reloads the
module, stubs ``boto3.Session`` with ``_FakeBoto3Session`` so we can
introspect ``botocore_session._credentials``.
"""
from __future__ import annotations

import importlib
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

aws_creds = pytest.importorskip(
    "factory.agent.runtime.adapters.aws_creds",
    reason="bd-5swj force_refresh helper not yet landed",
)


class _FakeBoto3Session:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw


def _setup_factory(mp: pytest.MonkeyPatch) -> Any:
    """Reset module singleton + stub boto3.Session; return factory."""
    import boto3
    mod = importlib.reload(aws_creds)
    mp.setattr(mod, "_SESSION", None, raising=False)
    mp.setattr(boto3, "Session", _FakeBoto3Session)
    for n in ("get_refreshable_session", "refreshable_session"):
        if callable(getattr(mod, n, None)):
            return getattr(mod, n)
    pytest.skip("aws_creds session factory not exposed")


# P-CR9 — force_refresh drops + rebuilds singleton ────────────────


def test_p_cr9_force_refresh_drops_singleton_fresh_deferred(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Idempotent on None; drops cache; fresh Deferred loads next values."""
    factory = _setup_factory(monkeypatch)
    # Idempotent when _SESSION is None — no raise, no boto resource touch.
    aws_creds.force_refresh()
    aws_creds.force_refresh()
    # Stub botocore.session.Session to return a different access_key per
    # rebuild; the Deferred refresher is invoked lazily on
    # get_frozen_credentials, so each call sees the next key.
    import botocore.session as _bs
    keys = iter(["AKIA-A", "AKIA-B"])

    class _F:
        def __init__(self, k: str) -> None:
            self.access_key, self.secret_key = k, "s"
            self.token, self.account_id = "t", "1"

    class _Rot:
        def get_credentials(self) -> Any:
            f = _F(next(keys))
            return type("_C", (), {"get_frozen_credentials": lambda s: f})()

    monkeypatch.setattr(_bs, "Session", lambda **kw: _Rot())
    s1 = factory()
    d1 = s1.kw["botocore_session"]._credentials
    f1 = d1.get_frozen_credentials()  # consumes "AKIA-A".
    aws_creds.force_refresh()
    s2 = factory()
    d2 = s2.kw["botocore_session"]._credentials
    f2 = d2.get_frozen_credentials()  # consumes "AKIA-B" via NEW deferred.
    assert id(s1) != id(s2), "force_refresh did not produce a new session"
    assert d1 is not d2, "rebuild reused the same Deferred — singleton leak"
    assert d1.method == d2.method == "companion-x-disk-refresh"
    assert (f1.access_key, f2.access_key) == ("AKIA-A", "AKIA-B"), (
        "rebuilt deferred did not load fresh disk values"
    )


# P-CR10 — force_refresh idempotency under threading ──────────────


def test_p_cr10_force_refresh_concurrent_no_deadlock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """8-way race on force_refresh; P-CR5 invariant still holds after."""
    factory = _setup_factory(monkeypatch)
    factory()  # seed singleton.
    b1 = threading.Barrier(8)

    def _refresh(_i: int) -> None:
        b1.wait()
        aws_creds.force_refresh()

    # 8 workers race on force_refresh — must not raise, must not deadlock.
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_refresh, range(8)))
    # Sequence: A force_refresh, B force_refresh, A get, B get →
    # both see same fresh singleton.
    aws_creds.force_refresh()
    aws_creds.force_refresh()
    assert id(factory()) == id(factory()), (
        "post-sequential-refresh singleton broken"
    )
    # Race the gets after a final refresh — P-CR5 invariant holds.
    aws_creds.force_refresh()
    b2 = threading.Barrier(8)

    def _build(_i: int) -> int:
        b2.wait()
        return id(factory())

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(_build, range(8)))
    assert len(set(ids)) == 1, f"P-CR5 broken after refresh: {len(set(ids))}"
