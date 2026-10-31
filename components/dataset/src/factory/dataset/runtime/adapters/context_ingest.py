"""Context ingest stage for the CAN failure-prediction pipeline.

Stage 0 of the CAN failure-prediction pipeline. Produces canonical
``environment_context`` records that downstream stages (can_ingest,
can_window, can_augment) merge with CAN frame data to enrich each
record with environmental, geospatial, and vehicle metadata.

Supported sources (selected via the ``sources`` list in the recipe):

* ``weather_openweathermap`` — OpenWeatherMap historical ``timemachine`` API
* ``gps_can``                — extract lat/lon/speed from decoded CAN signals
* ``vehicle_metadata``       — load static vehicle info from CSV/TSV/JSON

The adapter is intentionally tolerant of missing inputs: a partial
configuration (e.g. only GPS, no weather key) still yields a valid
context record with empty sub-objects for the missing sources, so
downstream merges remain shape-stable. API keys come from
``config["weather_api_key"]`` and are never persisted in recipes.

Pure per-source fetchers live in :mod:`_context_ingest_helpers` to keep
this file under the 200 LOC factory ceiling.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from ._context_ingest_helpers import (
    VALID_SOURCES,
    extract_gps_from_can,
    fetch_openweathermap,
    load_vehicle_metadata,
    parse_time_range,
)
from .context_record import build_context_record


class ContextIngestStageAdapter:
    """Adapter that ingests environmental context for the CAN pipeline.

    Implements :class:`factory.dataset.runtime.ports.DatasetStagePort`
    so it slots into the recipe stage map alongside the other CAN
    adapters. ``name`` matches the recipe stage ID; ``stage_version``
    is a stable identifier for checkpoint lineage.
    """

    name = "context_ingest"
    stage_version = "factory-context-ingest-1"
    allowed_config = frozenset({
        "sources", "time_range", "location", "vehicle_id",
        "weather_api_key", "input_uri", "input_uris",
    })

    def execute(
        self,
        records: Iterable[Any],
        config: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield one canonical context record merging every requested source."""
        values = dict(config or {})
        unknown = set(values) - self.allowed_config
        if unknown:
            raise ValueError(
                f"Unsupported context_ingest configuration: {sorted(unknown)}"
            )

        sources = list(values.get("sources") or [])
        if not sources:
            raise ValueError("context_ingest requires non-empty 'sources' config")
        bad_sources = [s for s in sources if s not in VALID_SOURCES]
        if bad_sources:
            raise ValueError(
                f"Unsupported context sources: {bad_sources}; "
                f"valid options: {sorted(VALID_SOURCES)}"
            )

        # Consume upstream records iterable — context_ingest sources its
        # own data, but honors the DatasetStagePort streaming contract.
        for _ in records:
            pass

        vehicle_id = str(values.get("vehicle_id") or "unknown")
        window_start, window_end = parse_time_range(values.get("time_range"))
        location = values.get("location")
        api_key = values.get("weather_api_key")
        input_uris = list(values.get("input_uris") or [])
        if values.get("input_uri"):
            input_uris.insert(0, str(values["input_uri"]))

        # Each source is independently optional; every typed input is tried
        # without collapsing distinct source artifacts onto one URI.
        weather = (
            fetch_openweathermap(location, window_start, window_end, api_key)
            if "weather_openweathermap" in sources else None
        )
        gps = (
            _first_loaded(input_uris, extract_gps_from_can)
            if "gps_can" in sources else None
        )
        vehicle = (
            _first_loaded(input_uris, lambda uri: load_vehicle_metadata(uri, vehicle_id))
            if "vehicle_metadata" in sources else None
        )

        yield build_context_record(
            vehicle_id=vehicle_id,
            window_start=window_start,
            window_end=window_end,
            weather=weather,
            gps=gps,
            vehicle=vehicle,
        )


def _first_loaded(uris: list[str], loader):
    for uri in uris:
        value = loader(uri)
        if value is not None:
            return value
    return None
