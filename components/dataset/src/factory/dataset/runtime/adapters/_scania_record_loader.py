"""SCANIA record loader for the can_synthesize hybrid pipeline.

Bridges a ``scania_data_uri`` (file://, directory, or single CSV) to a
list of ``{class, features}`` records that the
:class:`ScaniaPatternExtractor` consumes. Kept out of
:mod:`can_synthesize_hybrid_helpers` so that file stays under the
200-LOC factory ceiling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ._can_synthesize_hybrid_utils import uri_to_path


def load_scania_records(scania_data_uri: str) -> list[dict[str, Any]]:
    """Return ``[{class, features}, ...]`` from a SCANIA APS CSV source."""
    # Imported lazily so this module loads even without the dataset brick
    # fully on the path (e.g. inside the can_synthesize standalone test).
    from ._scania_helpers import SCANIA_HEADER_LINES, SCANIA_NA_SENTINELS

    path = uri_to_path(scania_data_uri)
    candidates: list[Path] = []
    if path.is_dir():
        candidates.extend(sorted(path.glob("aps_failure_*.csv")))
    elif path.is_file() and path.suffix == ".csv":
        candidates.append(path)
    if not candidates:
        raise FileNotFoundError(
            f"No aps_failure_*.csv found under {scania_data_uri!r}",
        )
    frames = [
        pd.read_csv(p, skiprows=SCANIA_HEADER_LINES, na_values=list(SCANIA_NA_SENTINELS))
        for p in candidates
    ]
    df = pd.concat(frames, ignore_index=True)
    feature_cols = [c for c in df.columns if c != "class"]
    return [
        {
            "class": str(row["class"]).strip().lower(),
            "features": {c: row[c] for c in feature_cols},
        }
        for _, row in df.iterrows()
    ]
