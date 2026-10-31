"""Context augmentation stage for the CAN failure-prediction pipeline.

Stage that aligns canonical ``environment_context`` records (from
``context_ingest``) with canonical ``can_frame`` records (from
``can_ingest`` or any downstream stage) and attaches a flat ``context``
sub-object to every CAN record. Downstream synthesis and ML stages
consume those features directly.

Three merge strategies are supported (recipe-selectable via
``merge_strategy``):

* ``nearest``    — pick the context record whose window midpoint is
  closest to the frame's ``timestamp_ns`` (smallest absolute gap).
* ``interpolate``— when the frame falls between two context records,
  linearly interpolate numeric fields by the relative position of
  ``timestamp_ns`` between the two window starts. Non-numeric fields
  take the value from the closer record.
* ``last_known``— use the most recent context record with
  ``window_start <= timestamp_ns`` (falls back to the first record
  when the frame precedes every context window).

``max_time_delta_s`` is the hard gap ceiling — frames outside any
context window by more than that interval get an empty ``context``
payload (filled via ``fill_strategy``). This guards against the
classic "context_ingest ran with the wrong ``time_range``" failure
mode where every frame would otherwise silently match a stale
window.

Pure path / field-extraction / interpolation helpers live in
:mod:`_context_augment_helpers` to keep this module under the 200-LOC
factory ceiling.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from ._context_augment_helpers import (
    DEFAULT_CONTEXT_FIELDS,
    _index_context_records,
)
from ._context_augment_match import _apply_fill, _match_context
from .context_prior import context_provenance


class ContextAugmentStageAdapter:
    """Adapter that enriches CAN frame records with environment context.

    Implements :class:`factory.dataset.runtime.ports.DatasetStagePort`
    so it slots into the recipe stage map. ``name`` matches the recipe
    stage ID; ``stage_version`` is a stable identifier for checkpoint
    lineage.
    """

    name = "context_augment"
    stage_version = "factory-context-augment-1"
    allowed_config = frozenset({
        "merge_strategy", "max_time_delta_s", "context_fields",
        "fill_strategy", "input_uri", "context_uri",
    })

    def execute(
        self,
        records: Iterable[Any],
        config: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield every CAN record with a ``context`` sub-object attached."""
        values = dict(config or {})
        unknown = set(values) - self.allowed_config
        if unknown:
            raise ValueError(
                f"Unsupported context_augment configuration: {sorted(unknown)}"
            )

        merge_strategy = str(values.get("merge_strategy", "nearest")).lower()
        if merge_strategy not in ("nearest", "interpolate", "last_known"):
            raise ValueError(f"Unsupported merge_strategy: {merge_strategy!r}")
        fill_strategy = str(values.get("fill_strategy", "null")).lower()
        if fill_strategy not in ("null", "mean", "last_known"):
            raise ValueError(f"Unsupported fill_strategy: {fill_strategy!r}")
        max_delta_s = float(values.get("max_time_delta_s", 3600.0))
        if max_delta_s <= 0:
            raise ValueError("max_time_delta_s must be > 0")

        # Resolve which fields to merge (flat dotted names). ``None`` →
        # the canonical default set so a typical recipe needs no
        # explicit ``context_fields`` config.
        requested = values.get("context_fields")
        fields = list(DEFAULT_CONTEXT_FIELDS if requested is None else requested)

        record_list = list(records)
        input_uri = values.get("input_uri")
        if not record_list and input_uri:
            from ..helpers import load_records_from_uri
            record_list = load_records_from_uri(input_uri)

        # Standalone / test path: load context records from a JSONL
        # ``file://`` URI when the materializer hands us no upstream
        # records (mirrors can_profile / can_window behavior).
        context_records: list[dict[str, Any]] = []
        context_uri = values.get("context_uri")
        if context_uri:
            from ..helpers import load_records_from_uri
            context_records = load_records_from_uri(context_uri)
        elif not record_list:
            context_records = []

        ctx_index = _index_context_records(context_records)
        max_delta_ns = int(max_delta_s * 1_000_000_000)

        for rec in record_list:
            if not isinstance(rec, dict):
                yield rec
                continue
            matched = _match_context(
                rec, ctx_index, fields, merge_strategy, max_delta_ns,
            )
            payload = _apply_fill(matched, fields, fill_strategy, ctx_index)
            out = dict(rec)
            out["context"] = payload
            out["context_provenance"] = context_provenance(
                rec, ctx_index, merge_strategy, max_delta_ns,
                fill_strategy, payload,
            )
            yield out


__all__ = ["ContextAugmentStageAdapter"]
