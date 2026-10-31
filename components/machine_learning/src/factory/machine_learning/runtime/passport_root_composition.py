"""ModelPassport root selection at the TrackingRuntime composition boundary."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_ENV = "ML_MODEL_PASSPORT_ROOT"


def capture_passport_root(
    config: dict[str, Any], passport_service: Any = None,
) -> Path | None:
    """Capture service > config > environment precedence without requiring a root."""
    candidates = (
        getattr(passport_service, "storage_root", None),
        config.get("model_passport_root"),
        os.environ.get(_ENV),
    )
    for candidate in candidates:
        if candidate is not None and str(candidate).strip():
            return Path(candidate).expanduser().absolute()
    return None


__all__ = ["capture_passport_root"]
