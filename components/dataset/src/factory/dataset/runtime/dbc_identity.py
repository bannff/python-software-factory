"""Pure canonical identifiers shared by Dataset exports and Graph declarations."""
from __future__ import annotations

import re


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "unnamed"


def dbc_version_identity(sha256: str) -> str:
    if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
        raise ValueError("DBC identity requires a lowercase SHA-256")
    return f"dbc-{sha256}"


def dbc_message_identity(sha256: str, arbitration_id: int, extended: bool = False) -> str:
    prefix = dbc_version_identity(sha256)
    return f"{prefix}-msg-{'x' if extended else 's'}-{arbitration_id:x}"


def dbc_signal_identity(
    sha256: str, arbitration_id: int, signal_name: str, extended: bool = False,
) -> str:
    message = dbc_message_identity(sha256, arbitration_id, extended)
    return f"signal-{message[4:]}-{_slug(signal_name)}"


__all__ = ["dbc_message_identity", "dbc_signal_identity", "dbc_version_identity"]
