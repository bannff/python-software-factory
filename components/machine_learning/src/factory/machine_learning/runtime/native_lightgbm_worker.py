"""Private entry point for one typed native LightGBM child operation."""
from __future__ import annotations

import json
import sys

try:
    from .native_lightgbm_contracts import (
        REQUEST_ADAPTER, FitRequest, NativeFailure, NativeSuccess, ScoreRequest,
    )
except ImportError:  # Direct fixed-path execution avoids eager package imports.
    from native_lightgbm_contracts import (
        REQUEST_ADAPTER, FitRequest, NativeFailure, NativeSuccess, ScoreRequest,
    )

_MAX_INPUT = 65_536


def _error_text(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    clean = "".join(char if 32 <= ord(char) < 127 else " " for char in text)
    return clean[:512] or "native operation failed"


def run(raw: bytes):
    request = REQUEST_ADAPTER.validate_json(raw, strict=True)
    try:
        from .native_lightgbm_ops import fit_predict_persist, inspect, score
    except ImportError:
        from native_lightgbm_ops import fit_predict_persist, inspect, score
    if isinstance(request, FitRequest):
        result = fit_predict_persist(request.payload)
    elif isinstance(request, ScoreRequest):
        result = score(request.operation, request.payload)
    else:
        result = inspect(request.operation, request.payload)
    return NativeSuccess(ok=True, operation=request.operation, result=result)


def main() -> None:
    raw = sys.stdin.buffer.read(_MAX_INPUT + 1)
    if len(raw) > _MAX_INPUT:
        raise SystemExit(2)
    try:
        response = run(raw)
    except Exception as exc:
        try:
            request = REQUEST_ADAPTER.validate_json(raw, strict=True)
        except Exception:
            raise SystemExit(2) from None
        response = NativeFailure(
            ok=False, operation=request.operation, error=_error_text(exc),
        )
    payload = response.model_dump(mode="json")
    sys.stdout.buffer.write(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode())


if __name__ == "__main__":
    main()
