"""Mint-once local protected-content keys for the Companion-X launcher.

Stores encrypted at rest (owner secrets, credential slots, protected artifacts)
fail closed without these keys. Unlike the per-run MCP token they must outlive
the process: rotating them would orphan every stored secret. Emits ``export``
lines for the launcher; a key the operator already set is never overridden,
checked per key.
"""
from __future__ import annotations

import base64
import fcntl
import json
import os
import stat
import sys
from pathlib import Path

KEK = "FACTORY_PROTECTED_CONTENT_LOCAL_KEK"
INDEX = "FACTORY_PROTECTED_CONTENT_LOCAL_INDEX_KEY"
NAMES = (KEK, INDEX)


class KeyFileError(RuntimeError):
    """The persisted key file is unsafe or unreadable; never silently replaced."""


def _read(path: Path) -> dict[str, str] | None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise KeyFileError(f"cannot open {path}: {error}") from error
    with os.fdopen(descriptor) as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise KeyFileError(f"{path} is not a regular file owned by you")
        if stat.S_IMODE(info.st_mode) != 0o600:
            raise KeyFileError(f"{path} must be mode 0600; run chmod 600 on it")
        try:
            keys = json.load(handle)
        except json.JSONDecodeError as error:
            raise KeyFileError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(keys, dict) or not all(isinstance(keys.get(n), str) for n in NAMES):
        raise KeyFileError(f"{path} does not hold both keys")
    return keys


def _write_atomically(path: Path, keys: dict[str, str]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(keys, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)  # readers see the whole file or none


def _load_or_create(path: Path) -> dict[str, str]:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = os.open(path.with_name(path.name + ".lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock) as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)  # concurrent first launches share one pair
        keys = _read(path)
        if keys is None:
            keys = {name: base64.b64encode(os.urandom(32)).decode() for name in NAMES}
            _write_atomically(path, keys)
        return keys


def exports(path: Path, environ: dict[str, str]) -> list[str]:
    missing = [name for name in NAMES if not environ.get(name)]
    if not missing:
        return []
    keys = _load_or_create(path)
    return [f"export {name}={keys[name]}" for name in missing]


if __name__ == "__main__":
    try:
        print("\n".join(exports(Path(sys.argv[1]), dict(os.environ))))
    except KeyFileError as error:
        sys.exit(f"local protected keys: {error}")
