"""Refreshable AWS credentials for ``BedrockModel`` clients (bd-4kq2, bd-5swj).

Strands ``BedrockModel`` builds its boto3 client ONCE in ``__init__``
(``strands/models/bedrock.py:152-204``); the client carries a frozen
``Credentials`` object. After the credential helper rotates ``~/.aws/credentials`` or
the laptop sleeps long enough for in-memory creds to expire, cached
agents fail the next ``ConverseStream`` with ``ExpiredTokenException``.

Strands gap: ``BedrockModel.__init__`` accepts ``boto_session=`` (docs
§1.3 *Setting Up AWS Credentials* Option 3) but the docs only show
static-credential forms. ``botocore`` provides
``DeferredRefreshableCredentials`` but ``CredentialResolver`` is
discovery-only chained — no public install hook for an in-memory custom
refresher. Per the AWS recipe at
https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html#refreshable-credentials
the canonical seam is ``botocore.session.Session._credentials``; we
assign the deferred refresher there and wrap a ``boto3.Session``.

SDK-First "build it but document the gap" guards: (a) this docstring;
(b) ``test_aws_creds_canary.py`` pinning ``create_from_metadata``,
``DeferredRefreshableCredentials._refresh_using``,
``BedrockModel(boto_session=...)``; (c) ``botocore>=1.34,<2`` pin in
``components/agent/BRICK.yaml``. the credential helper writes no ``expiration``, so
the callback synthesizes ``expiry_time = now_utc + ttl``.

TTL choice (bd-5swj): ``_DEFAULT_TTL_SECONDS = 1800`` (30 min). Botocore's
``RefreshableCredentials._advisory_refresh_timeout`` defaults to 900s
(``botocore/credentials.py``); ``refresh_needed`` (l. 555) returns True
once ``expiry_time - now <= advisory``. With TTL=1800 the advisory
window opens at t0+15min — a sane re-read cadence inside the helper's ~6h
rotation. An earlier TTL=900 made the synthetic window equal the
advisory window, so ``refresh_needed`` flipped True after t0+ε on every
call and triggered a full disk read on every Bedrock invocation.
``COMPANION_X_AWS_CRED_REFRESH_SECONDS`` overrides for ops dial-in.

``force_refresh()`` contract (bd-5swj): callers MUST invoke
``force_refresh()`` BEFORE rebuilding any cached agent / boto client
that observed an ``ExpiredTokenException``. Without it the rebuild
re-binds the same singleton ``boto3.Session`` whose underlying
``DeferredRefreshableCredentials`` still holds a stale frozen snapshot,
and the rebuild silently observes the same expired creds. ``close()``
+ rebuild without a preceding ``force_refresh()`` is a no-op for the
expired-token case — that is precisely the bug bd-5swj fixes.

Module-level singleton so all sites share one ``_LOCK`` + metadata
cache; ``profile`` is closure-captured.
"""
from __future__ import annotations

import datetime
import os
import threading
import time
from typing import Any

import boto3
import botocore.session
from botocore.credentials import DeferredRefreshableCredentials

from factory.llm_gateway.interface import (
    AgentCredentialError, no_credential_message,
)

_DEFAULT_TTL_SECONDS = 1800  # 30 min; advisory window opens at t0+15min.
_DISK_READ_RETRIES = 3
_DISK_READ_BACKOFF_S = 0.05

_SESSION: boto3.Session | None = None
_LOCK = threading.Lock()


def _freeze_credentials(
    bs: botocore.session.Session, profile: str | None,
) -> Any:
    """Resolve botocore's credentials once; fail TYPED when none resolve.

    ``botocore`` raises a bare ``AttributeError`` (``'NoneType' object has no
    attribute 'get_frozen_credentials'``) when the resolver finds nothing —
    exactly the noise that buried the real problem under the side-chat
    planner's "profile () could not be found" (epic #124 S3). Any missing-
    or broken-credentials outcome here is instead a named
    :class:`AgentCredentialError`.
    """
    try:
        frozen = bs.get_credentials().get_frozen_credentials()
    except AgentCredentialError:
        raise
    except (IOError, PermissionError):
        raise  # retryable by the caller's disk-read loop
    except Exception as exc:
        raise AgentCredentialError(no_credential_message("bedrock", exc)) from exc
    if frozen is None:
        raise AgentCredentialError(
            f"no AWS credentials resolve for profile={profile!r} — "
            "configure AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or AWS_PROFILE",
        )
    return frozen


def _read_creds_from_disk(profile: str | None) -> dict[str, Any]:
    """Re-walk profile→env→IMDS and return a refresh metadata dict."""
    last_err: Exception | None = None
    for _ in range(_DISK_READ_RETRIES):
        try:
            bs = botocore.session.Session(profile=profile)
            frozen = _freeze_credentials(bs, profile)
            ttl = int(os.environ.get(
                "COMPANION_X_AWS_CRED_REFRESH_SECONDS", _DEFAULT_TTL_SECONDS,
            ))
            expiry = (datetime.datetime.now(datetime.timezone.utc)
                      + datetime.timedelta(seconds=ttl))
            metadata: dict[str, Any] = {
                "access_key": frozen.access_key,
                "secret_key": frozen.secret_key,
                "token": frozen.token,
                "expiry_time": expiry.isoformat(),
            }
            account_id = getattr(frozen, "account_id", None)
            if account_id:
                metadata["account_id"] = account_id
            return metadata
        except (IOError, PermissionError) as exc:
            last_err = exc
            time.sleep(_DISK_READ_BACKOFF_S)
    raise AgentCredentialError(
        f"Failed to read AWS credentials for profile={profile!r} "
        f"after {_DISK_READ_RETRIES} attempts ({last_err})"
    ) from last_err


def get_refreshable_session(profile: str | None = None) -> boto3.Session:
    """Process-wide ``boto3.Session`` with refreshable creds (singleton)."""
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    with _LOCK:
        if _SESSION is not None:
            return _SESSION
        creds = DeferredRefreshableCredentials(
            refresh_using=lambda: _read_creds_from_disk(profile),
            method="companion-x-disk-refresh",
        )
        bs = botocore.session.Session()
        bs._credentials = creds  # private-attr seam — see module docstring.
        _SESSION = boto3.Session(botocore_session=bs)
        return _SESSION


def force_refresh() -> None:
    """Drop the cached session so the next ``get_refreshable_session()`` rebuilds (bd-5swj).

    Resets the module-level ``_SESSION`` singleton to ``None`` under
    ``_LOCK``. Idempotent — safe to call concurrently and safe to call
    when no session has been built yet.

    Contract: callers MUST invoke this BEFORE rebuilding any cached
    Strands ``Agent`` / ``BedrockModel`` / boto client that just observed
    an ``ExpiredTokenException``. Rebuilding without this call re-binds
    against the same singleton session and the new client observes the
    same stale creds — the no-op bug bd-5swj fixes. See module docstring.
    """
    global _SESSION
    with _LOCK:
        _SESSION = None


__all__ = ["get_refreshable_session", "force_refresh"]
