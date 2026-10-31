"""Typed boundary models for the KB brick."""

from .ingest import KbIngestRequest, KbIngestResult
from .ops import (
    KbBackfillRequest, KbBackfillResult, KbDeleteDocumentResult,
    KbDocumentIdRequest, KbGetDocumentResult, KbListDocumentsRequest,
    KbListDocumentsResult, KbSearchHit, KbSearchRequest, KbSearchResult,
)
from .surface import (
    KbAuthoringDeleteRequest, KbAuthoringResult, KbAuthoringStatusResult,
    KbAuthoringUpsertRequest, KbAuthoringValidateRequest, KbCapabilitiesResult,
    KbCollectionRegistryResult, KbCollectionStatsRequest, KbCollectionStatsResult,
    KbConfigSchemaResult, KbEmptyRequest, KbHealthResult,
)

__all__ = [
    "KbAuthoringDeleteRequest", "KbAuthoringResult", "KbAuthoringStatusResult",
    "KbAuthoringUpsertRequest", "KbAuthoringValidateRequest", "KbBackfillRequest",
    "KbBackfillResult", "KbCapabilitiesResult", "KbCollectionRegistryResult",
    "KbCollectionStatsRequest", "KbCollectionStatsResult", "KbConfigSchemaResult",
    "KbDeleteDocumentResult", "KbDocumentIdRequest", "KbEmptyRequest",
    "KbGetDocumentResult", "KbHealthResult", "KbIngestRequest", "KbIngestResult",
    "KbListDocumentsRequest", "KbListDocumentsResult", "KbSearchHit", "KbSearchRequest",
    "KbSearchResult",
]
