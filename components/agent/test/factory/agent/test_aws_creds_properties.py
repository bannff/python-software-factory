"""bd-4kq2 adversarial properties — companion to test_aws_creds_canary.

Memos: strands-expert ``5d44a58e``, meta-architect ``e923f7ce``.
P-CR1 credential-helper mid-write race: ≤2 IO retry, 3+ raise chained, non-IO no-retry.
P-CR2 tz-aware expiry (naive breaks botocore ``_seconds_remaining``).
P-CR3 ``COMPANION_X_AWS_CRED_REFRESH_SECONDS`` honored or sane fallback.
P-CR4 profile threaded into closure, NOT mutated into ``os.environ``.
P-CR5 module-level singleton across calls + threads.
"""
from __future__ import annotations

import datetime as _dt
import importlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any

import pytest
from dateutil.parser import parse as _parse_dt
from hypothesis import given, settings, strategies as st

aws_creds = pytest.importorskip(
    "factory.agent.runtime.adapters.aws_creds",
    reason="bd-4kq2 helper not yet landed",
)
_RETRY = (IOError, PermissionError, FileNotFoundError, OSError)


def _disk_reader(mod: Any) -> Any:
    for n in ("_read_creds_from_disk", "read_creds_from_disk"):
        if callable(getattr(mod, n, None)):
            return getattr(mod, n)
    pytest.skip("aws_creds disk-reader not exposed")

def _factory(mod: Any) -> Any:
    for n in ("get_refreshable_session", "refreshable_session"):
        if callable(getattr(mod, n, None)):
            return getattr(mod, n)
    pytest.skip("aws_creds session factory not exposed")

def _read(fn: Any) -> dict:
    try: return fn(None)
    except TypeError: return fn()

def _to_dt(raw: Any) -> _dt.datetime:
    return raw if isinstance(raw, _dt.datetime) else _parse_dt(raw)

class _Stub:
    def __init__(self, script: list[BaseException | None]) -> None:
        self.script = list(script)
    def get_credentials(self) -> Any:
        head = self.script.pop(0)
        if isinstance(head, BaseException): raise head
        class _F:
            access_key, secret_key = "AKIA-FAKE", "fake-secret"
            token, account_id = "fake-tok", "123456789012"
        class _C:
            def get_frozen_credentials(self_inner) -> Any: return _F()
        return _C()

@contextmanager
def _disk_ctx(script: list[BaseException | None]):
    import botocore.session as _bs
    orig = _bs.Session
    stub = _Stub(script)  # share across retries
    _bs.Session = lambda **kw: stub  # type: ignore[assignment]
    try: yield
    finally: _bs.Session = orig  # type: ignore[assignment]

@contextmanager
def _env_ctx(name: str, value: str | None):
    prior = os.environ.get(name)
    if value is None: os.environ.pop(name, None)
    else: os.environ[name] = value
    try: yield
    finally:
        if prior is None: os.environ.pop(name, None)
        else: os.environ[name] = prior


# P-CR1 credential-helper mid-write race ────────────────────────────────────────
@given(n=st.integers(0, 2), err=st.sampled_from(_RETRY))
@settings(max_examples=30, deadline=None)
def test_p_cr1_io_under_threshold_retries(n: int, err: type) -> None:
    fn = _disk_reader(aws_creds)
    with _disk_ctx([err("flap")] * n + [None]):
        out = _read(fn)
    assert out["access_key"] == "AKIA-FAKE" and "expiry_time" in out

@given(err=st.sampled_from(_RETRY))
@settings(max_examples=8, deadline=None)
def test_p_cr1_three_io_errors_raise_chained(err: type) -> None:
    fn = _disk_reader(aws_creds)
    with _disk_ctx([err("perma")] * 3), pytest.raises(Exception) as ei:
        _read(fn)
    chained = ei.value.__cause__ or ei.value.__context__ or ei.value
    assert isinstance(chained, err) or isinstance(ei.value, err)

def test_p_cr1_non_io_does_not_retry() -> None:
    fn = _disk_reader(aws_creds)
    with _disk_ctx([RuntimeError("synthetic"), None, None]), \
            pytest.raises(BaseException) as ei:
        _read(fn)
    err = ei.value
    if not isinstance(err, RuntimeError):
        assert isinstance(err.__cause__ or err.__context__, RuntimeError)

# P-CR2 tz-aware expiry ───────────────────────────────────────────
def test_p_cr2_expiry_is_tz_aware() -> None:
    fn = _disk_reader(aws_creds)
    with _disk_ctx([None]):
        assert _to_dt(_read(fn)["expiry_time"]).tzinfo is not None

# P-CR3 env override ──────────────────────────────────────────────
@given(seconds=st.integers(120, 7200))
@settings(max_examples=20, deadline=None)
def test_p_cr3_env_override_valid(seconds: int) -> None:
    fn = _disk_reader(aws_creds)
    with _env_ctx("COMPANION_X_AWS_CRED_REFRESH_SECONDS", str(seconds)), \
            _disk_ctx([None]):
        before = _dt.datetime.now(_dt.timezone.utc)
        delta = (_to_dt(_read(fn)["expiry_time"]) - before).total_seconds()
    assert seconds - 5 <= delta <= seconds + 30

@given(bad=st.sampled_from(["abc", "12.5"]))
@settings(max_examples=10, deadline=None)
def test_p_cr3_env_override_invalid(bad: str) -> None:
    """Non-numeric raises ValueError. Negative/zero in xfail below."""
    fn = _disk_reader(aws_creds)
    with _env_ctx("COMPANION_X_AWS_CRED_REFRESH_SECONDS", bad), \
            _disk_ctx([None]), pytest.raises(ValueError):
        _read(fn)

@pytest.mark.xfail(reason="bd-4kq2: implementer accepts negative seconds; "
                   "follow-up bd. Should clamp >=60s or raise.",
                   strict=False)
@given(bad=st.sampled_from(["-1", "-3000", "0"]))
@settings(max_examples=5, deadline=None)
def test_p_cr3_env_override_negative_or_zero(bad: str) -> None:
    fn = _disk_reader(aws_creds)
    with _env_ctx("COMPANION_X_AWS_CRED_REFRESH_SECONDS", bad), \
            _disk_ctx([None]):
        try:
            out = _read(fn)
        except (ValueError, RuntimeError):
            return
    delta = (_to_dt(out["expiry_time"])
             - _dt.datetime.now(_dt.timezone.utc)).total_seconds()
    assert delta >= 60, f"got {delta}s for {bad!r} — expiry in past"

# P-CR4 + P-CR5 (factory + singleton) ─────────────────────────────
class _FakeBoto3Session:
    def __init__(self, **kw: Any) -> None: self.kw = kw

def _setup_factory(mp: pytest.MonkeyPatch) -> Any:
    """Reset module singleton + stub boto3.Session; return factory."""
    import boto3
    mod = importlib.reload(aws_creds)
    mp.setattr(mod, "_SESSION", None, raising=False)
    mp.setattr(boto3, "Session", _FakeBoto3Session)
    return _factory(mod)

def test_p_cr4_profile_no_environ_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = _setup_factory(monkeypatch)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    factory(profile="qa-test-profile-A")
    assert os.environ.get("AWS_PROFILE") != "qa-test-profile-A", (
        "factory mutated AWS_PROFILE — strands-expert verdict required "
        "closure-threaded profile"
    )

def test_p_cr5_singleton_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = _setup_factory(monkeypatch)
    assert id(factory()) == id(factory())

def test_p_cr5_singleton_thread_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = _setup_factory(monkeypatch)
    barrier = threading.Barrier(8)
    def _race(_i: int) -> int:
        barrier.wait()
        return id(factory())
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(_race, range(8)))
    assert len(set(ids)) == 1, f"race produced {len(set(ids))} sessions"

