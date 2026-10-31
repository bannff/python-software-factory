"""Write inline content into a sandbox environment.

Encoding-aware and adapter-agnostic: content arrives over MCP (utf8 or base64),
is staged to a host tempfile, then copied into the environment through whatever
``upload`` callable the adapter provides. No shell escaping, no caller-side
host staging.
"""
from __future__ import annotations

import base64
import os
import tempfile
from typing import Any, Awaitable, Callable

UploadFn = Callable[[str, str, str], Awaitable[dict[str, Any]]]


def decode_content(content: str, encoding: str) -> bytes:
    """Decode inline content; raises ``ValueError`` on malformed base64."""
    if encoding == "base64":
        return base64.b64decode(content, validate=True)
    return content.encode("utf-8")


async def write_file(
    upload: UploadFn, env_id: str, remote_path: str, content: str, encoding: str,
) -> dict[str, Any]:
    """Stage ``content`` to a host tempfile and upload it into the environment."""
    data = decode_content(content, encoding)
    fd, tmp = tempfile.mkstemp(prefix="sandbox-write-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        result = await upload(env_id, tmp, remote_path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    result["bytes_written"] = len(data)
    return result
