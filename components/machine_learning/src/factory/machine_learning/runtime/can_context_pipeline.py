"""Keystone CAN pipeline — context stage orchestration (machine_learning.runtime).

Opt-in context enrichment chain that runs between ``profile`` and ``synthesize``
in the keystone CAN pipeline. Each stage is submitted + polled individually so
failures are isolated and durations are auditable, matching the existing
keystone pattern in ``can_keystone.py``.

Stages
------
    1. context_ingest    — pull external context signals
    2. context_augment   — merge context into the decoded corpus
    3. context_correlate — emit an analytical correlation sidecar

The output of ``context_augment`` becomes the sampling source for
``synthesize`` when ``use_context=True``, replacing the raw decoded corpus.
The ``context_correlate`` artifact remains a non-sampling sidecar.

Also hosts ``sample_corpus_for_synth`` — the shared load+reservoir-sample
helper that fronts both the context-augmented and raw decoded corpora, so
``can_keystone.py`` stays under the 200 LOC tenet.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .can_keystone_helpers import (
    load_jsonl_windows,
    reservoir_sample,
    uri_to_path,
    write_sampled_jsonl,
)

# Built-in context recipe URIs; recipe_digest = sha256(uri.encode()) per
# ``_resolve_local_builtin_recipe`` in dataset.runtime.recipe.
_CONTEXT_RECIPE_URIS = {
    "context_ingest": "recipe://local/context-ingest@1",
    "context_correlate": "recipe://local/context-correlate@1",
    "context_augment": "recipe://local/context-augment@1",
}


def run_context_chain(
    *,
    ingest_dataset_uri: str,
    context_sources: list[str],
    config_overrides: dict[str, dict[str, Any]] | None,
    vehicle_id: str,
    snaps: Path,
    root: Path,
    run_stage: Any,
) -> dict[str, Any]:
    """Run context_ingest → augment → correlate with typed artifacts.

    The augmentation artifact is the corpus returned to synthesis. The
    correlation artifact is an analytical sidecar and never enters sampling.
    """
    if not context_sources:
        return {
            "error": "use_context=True requires non-empty context_sources",
            "stage": "context_ingest",
        }
    overrides = config_overrides or {}
    jobs: dict[str, str] = {}
    artifacts: dict[str, str] = {}

    ingest_inputs = [ingest_dataset_uri, *context_sources]
    ingest = run_stage(
        "context_ingest", _CONTEXT_RECIPE_URIS["context_ingest"], ingest_inputs,
        {"vehicle_id": vehicle_id, **dict(overrides.get("context_ingest") or {})},
        snaps, root, f"keystone:{vehicle_id}:context_ingest",
        input_roles=[
            "decoded_can", *[f"context_source:{index}" for index in range(len(context_sources))],
        ],
    )
    if "error" in ingest:
        return {"error": ingest["error"], "stage": "context_ingest", "job_id": ingest.get("job_id")}
    jobs["context_ingest"] = ingest["job_id"]
    artifacts["context_ingest"] = ingest["dataset_uri"]

    augment = run_stage(
        "context_augment", _CONTEXT_RECIPE_URIS["context_augment"],
        [ingest_dataset_uri, ingest["dataset_uri"]],
        dict(overrides.get("context_augment") or {}), snaps, root,
        f"keystone:{vehicle_id}:context_augment",
        input_roles=["decoded_can", "environment_context"],
    )
    if "error" in augment:
        return {"error": augment["error"], "stage": "context_augment", "job_id": augment.get("job_id")}
    jobs["context_augment"] = augment["job_id"]
    artifacts["context_augment"] = augment["dataset_uri"]

    correlate = run_stage(
        "context_correlate", _CONTEXT_RECIPE_URIS["context_correlate"],
        [augment["dataset_uri"]], dict(overrides.get("context_correlate") or {}),
        snaps, root, f"keystone:{vehicle_id}:context_correlate",
        input_roles=["context_augmented_can"],
    )
    if "error" in correlate:
        return {"error": correlate["error"], "stage": "context_correlate", "job_id": correlate.get("job_id")}
    jobs["context_correlate"] = correlate["job_id"]
    artifacts["context_correlate"] = correlate["dataset_uri"]
    return {
        "dataset_uri": augment["dataset_uri"],
        "correlation_uri": correlate["dataset_uri"],
        "jobs": jobs,
        "artifacts": artifacts,
    }


def sample_corpus_for_synth(
    corpus_uri: str, max_samples: int, vehicle_id: str, snaps: Path,
) -> dict[str, Any]:
    """Load + reservoir-sample any corpus URI; return sampled URI or error dict.

    Shared by the raw-ingest path and the context-augmented path so
    ``can_keystone.py`` doesn't duplicate the missing/empty/load-error
    guards around the JSONL artifact.
    """
    corpus_path = uri_to_path(corpus_uri)
    if corpus_path is None or not corpus_path.exists() or corpus_path.stat().st_size == 0:
        return {
            "error": "corpus artifact is missing or empty",
            "dataset_uri": corpus_uri,
        }
    try:
        records = load_jsonl_windows(str(corpus_path))
    except Exception as exc:
        return {
            "error": f"failed to load corpus artifact: {exc}",
            "dataset_uri": corpus_uri,
        }
    sampled_uri = write_sampled_jsonl(
        reservoir_sample(records, max_samples), snaps, vehicle_id,
    )
    return {"sampled_uri": sampled_uri}


__all__ = ["run_context_chain", "sample_corpus_for_synth"]
