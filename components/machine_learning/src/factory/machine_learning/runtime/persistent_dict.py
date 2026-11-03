"""A dict that survives restarts: every mutation rewrites one JSON file atomically.

The ML registries (base models, training defaults, datasets) were process-local,
so a registered base model vanished on restart. They are tiny and single-writer,
so a whole-file rewrite is simpler and safer than anything fancier.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)


def registry_dir() -> Path:
    """``ML_REGISTRY_DIR`` or a per-user data directory."""
    override = os.environ.get("ML_REGISTRY_DIR")
    return Path(override) if override else Path.home() / ".local" / "share" / "python-factory" / "ml"


class PersistentDict(dict):
    def __init__(
        self, name: str, *, encode: Callable[[Any], Any] = lambda v: v,
        decode: Callable[[Any], Any] = lambda v: v,
    ) -> None:
        super().__init__()
        self._path = registry_dir() / f"{name}.json"
        self._encode, self._decode = encode, decode
        try:
            if self._path.is_file():
                for key, value in json.loads(self._path.read_text()).items():
                    super().__setitem__(key, decode(value))
        except (OSError, ValueError, TypeError) as exc:
            # Never refuse to start over a damaged registry; say so and start empty.
            logger.warning("ignoring unreadable registry %s: %s", self._path, exc)

    def _flush(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps({k: self._encode(v) for k, v in self.items()}))
            os.replace(tmp, self._path)
        except OSError as exc:
            logger.error("could not persist registry %s: %s", self._path, exc)

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self._flush()

    def __delitem__(self, key: Any) -> None:
        super().__delitem__(key)
        self._flush()

    def update(self, *args: Any, **kwargs: Any) -> None:
        super().update(*args, **kwargs)
        self._flush()

    def pop(self, key: Any, *default: Any) -> Any:
        value = super().pop(key, *default)
        self._flush()
        return value

    def clear(self) -> None:
        super().clear()
        self._flush()

    def setdefault(self, key: Any, default: Any = None) -> Any:
        value = super().setdefault(key, default)
        self._flush()
        return value


__all__: Iterable[str] = ["PersistentDict", "registry_dir"]
