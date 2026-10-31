"""Credential and filesystem-path redaction for Test MCP projections."""
from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath
from typing import Any

_REDACTED = "[redacted]"
_KEY_NAMES = (
    r"aws_secret_access_key|aws_access_key_id|aws_session_token|"
    r"aws_security_token|secret[_-]?access[_-]?key|access[_-]?key(?:[_-]?id)?|"
    r"access[_-]?token|refresh[_-]?token|session[_-]?token|"
    r"client[_-]?secret|private[_-]?key|api[_-]?key|database_url|db_url|"
    r"password|secret|token|credentials?|credential"
)
_CREDENTIAL = re.compile(
    r"(?ix)(?<![\w-])(?P<key>\\?[\"']?(?:(?:[a-z0-9]+)[_-])*(?:"
    + _KEY_NAMES
    + r")\\?[\"']?)\s*(?P<sep>[:=])\s*"
    r"(?P<value>(?P<quote>\\?[\"'])(?:\\.|[^\"'\\])*(?P=quote)|\[[^\]\r\n]*\]|[^\s,;}\]>]+)"
)
_AUTHORIZATION = re.compile(
    r"(?ix)(?P<prefix>[\"']?\bAuthorization[\"']?\s*[:=]\s*"
    r"[\"']?(?:Bearer|Basic)\s+)(?P<value>[^\"'\s,;}]+)"
)
_AUTHORIZATION_BARE = re.compile(
    r"(?ix)(?P<prefix>\bAuthorization\s+(?:Bearer|Basic)\s+)"
    r"(?P<value>[^\s,;}]+)"
)
_URL_USERINFO = re.compile(
    r"(?i)(?P<prefix>\b[a-z][a-z0-9+.-]*://)[^/@\s]+@"
)
_PEM = re.compile(
    r"(?is)-----BEGIN [^-\r\n]+-----.*?(?:-----END [^-\r\n]+-----|$)"
)
_POSIX_PATH = re.compile(
    r'''(?<![\w])/+(?:[^/"'`,;)}\]\r\n]+/)*[^/"'`,;)}\]\r\n]+'''
)
_WINDOWS_PATH = re.compile(
    r'''(?<![\w-])(?:[A-Za-z]:[\\/]*|\\\\)(?:[^\\/\r\n"'`,;)}\]]+[\\/]+)*[^\\/\r\n"'`,;)}\]]+'''
)


def _is_absolute(value: str) -> bool:
    """Treat host paths, drive-relative paths, and URI paths as external."""
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
        return True
    if value.startswith(("/", "\\")):
        return True
    windows = PureWindowsPath(value)
    return windows.is_absolute() or bool(windows.drive)


def safe_relative_path(root: Path, value: str | Path) -> str | None:
    """Return a root-relative path, or ``None`` for an external absolute path."""
    raw = str(value)
    if _is_absolute(raw):
        if not raw.startswith("/") or raw.startswith("//"):
            return None
        candidate = Path(raw)
    else:
        candidate = root / raw
    try:
        relative = candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (OSError, ValueError):
        return None
    return relative.as_posix() or "."


def _identity_is_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return (
        _is_absolute(value)
        or normalized.startswith(".")
        or "/" in normalized
        or "\\" in value
        or ":" in normalized.split("/", 1)[0]
    )


def normalize_junit_identity(root: Path, identity: str) -> str:
    """Hide absolute and traversing JUnit file identities."""
    parts = identity.split("::", 2)
    if not parts or not _identity_is_path(parts[0]):
        return identity
    relative = safe_relative_path(root, parts[0])
    parts[0] = "<test-root>" if relative == "." else relative or "<external-path>"
    return "::".join(parts)


def _credential_replacement(match: re.Match[str]) -> str:
    quote = match.groupdict().get("quote") or ""
    return f"{match.group('key')}{match.group('sep')}{quote}{_REDACTED}{quote}"


def _replace_path_token(root: Path, raw: str) -> str:
    trimmed = raw.rstrip()
    trailing = raw[len(trimmed):]
    relative = safe_relative_path(root, trimmed)
    if relative is None:
        return "<path>" + trailing
    replacement = "<test-root>" if relative == "." else f"<test-root>/{relative}"
    return replacement + trailing


def _replace_paths(root: Path, text: str) -> str:
    variants = {str(root.resolve(strict=False))}
    variants |= {item.replace("/", "\\") for item in variants}
    for variant in sorted(variants, key=len, reverse=True):
        if len(variant) > 1:
            text = text.replace(variant, "<test-root>")
    text = _POSIX_PATH.sub(lambda match: _replace_path_token(root, match.group(0)), text)
    return _WINDOWS_PATH.sub(lambda match: _replace_path_token(root, match.group(0)), text)


def redact(root: Path, value: Any) -> str:
    """Redact credentials, URL userinfo, and absolute filesystem paths."""
    text = str(value)
    text = _PEM.sub(_REDACTED, text)
    text = _CREDENTIAL.sub(_credential_replacement, text)
    text = _AUTHORIZATION.sub(lambda match: match.group("prefix") + _REDACTED, text)
    text = _AUTHORIZATION_BARE.sub(
        lambda match: match.group("prefix") + _REDACTED, text
    )
    text = _URL_USERINFO.sub(lambda match: match.group("prefix") + "<redacted>@", text)
    return _replace_paths(root, text)
