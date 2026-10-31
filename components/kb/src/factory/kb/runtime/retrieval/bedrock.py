"""Bedrock Knowledge Base adapter — GraphRAG via Neptune Analytics.

Implements VectorStore for AWS Bedrock Knowledge Bases. search() calls
bedrock-agent-runtime:Retrieve. health_check() calls GetKnowledgeBase.
Ingestion is handled externally (Glue pipeline), not by this adapter.

KB ID resolved from: env KB_BEDROCK_KB_ID → SSM /art/ml/bedrock/gt-kb-id.
Activated via kb.backend=bedrock in config brick.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from pydantic import BaseModel, Field

from ..models import Document, SearchResult
from ..ports import VectorStore

logger = logging.getLogger(__name__)

_DEFAULT_SSM_PATH = "/art/ml/bedrock/gt-kb-id"
_DEFAULT_REGION = "us-east-1"


class BedrockKBConfig(BaseModel):
    """Configuration for Bedrock Knowledge Base adapter."""

    kb_id: str = Field(..., description="Bedrock Knowledge Base ID")
    region: str = Field(default=_DEFAULT_REGION, description="AWS region")
    model_arn: str | None = Field(
        default=None,
        description="Model ARN for retrieval (optional, uses KB default)",
    )

    model_config = {"extra": "forbid"}


def _resolve_kb_id() -> str:
    """Resolve KB ID from env var or SSM parameter."""
    env_val = os.environ.get("KB_BEDROCK_KB_ID")
    if env_val:
        return env_val

    try:
        from factory.config.interface import get_infra
        return get_infra("kb.bedrock.kb_id", "")
    except ImportError:
        pass

    # Direct SSM lookup as last resort
    try:
        import boto3
        ssm = boto3.client("ssm", region_name=_DEFAULT_REGION)
        resp = ssm.get_parameter(Name=_DEFAULT_SSM_PATH)
        return resp["Parameter"]["Value"]
    except Exception as e:
        logger.error("Failed to resolve Bedrock KB ID from SSM: %s", e)
        raise ValueError(
            "Bedrock KB ID not found. Set KB_BEDROCK_KB_ID env var "
            f"or publish to SSM at {_DEFAULT_SSM_PATH}"
        ) from e


class BedrockKBVectorStore(VectorStore):
    """Bedrock Knowledge Base adapter using Retrieve API."""

    def __init__(self, config: BedrockKBConfig | None = None) -> None:
        import boto3

        if config is None:
            config = BedrockKBConfig(kb_id=_resolve_kb_id())
        self._config = config
        self._agent_client = boto3.client(
            "bedrock-agent", region_name=config.region,
        )
        self._runtime_client = boto3.client(
            "bedrock-agent-runtime", region_name=config.region,
        )
        logger.info(
            "Bedrock KB adapter initialized: kb_id=%s region=%s",
            config.kb_id, config.region,
        )

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Call bedrock-agent-runtime:Retrieve and map to SearchResult."""
        kwargs: dict[str, Any] = {
            "knowledgeBaseId": self._config.kb_id,
            "retrievalQuery": {"text": query},
            "retrievalConfiguration": {
                "vectorSearchConfiguration": {
                    "numberOfResults": limit,
                },
            },
        }
        if filters:
            kwargs["retrievalConfiguration"]["vectorSearchConfiguration"][
                "filter"
            ] = _build_filter(filters)

        try:
            resp = self._runtime_client.retrieve(**kwargs)
        except Exception as e:
            logger.error("Bedrock Retrieve failed: %s", e)
            return []

        return _parse_retrieve_response(resp)

    def add(self, document: Document, **kwargs: Any) -> None:
        """Ingestion is handled by the Glue pipeline, not this adapter."""
        raise NotImplementedError(
            "Bedrock KB ingestion is managed by the Glue pipeline. "
            "Use StartIngestionJob or the Glue console to sync data."
        )

    def delete(self, document_id: str) -> bool:
        """Document deletion not supported via Bedrock KB API."""
        raise NotImplementedError(
            "Bedrock KB document deletion is managed by the data source."
        )

    def get(self, document_id: str) -> Document | None:
        """Individual document retrieval not supported by Retrieve API."""
        logger.warning("get() not supported for Bedrock KB adapter")
        return None

    def list_documents(self, limit: int = 100) -> list[Document]:
        """Document listing not supported by Bedrock KB API."""
        logger.warning("list_documents() not supported for Bedrock KB")
        return []

    def health_check(self) -> dict[str, Any]:
        """Call GetKnowledgeBase to verify the KB is ACTIVE."""
        try:
            resp = self._agent_client.get_knowledge_base(
                knowledgeBaseId=self._config.kb_id,
            )
            kb = resp.get("knowledgeBase", {})
            status = kb.get("status", "UNKNOWN")
            return {
                "healthy": status == "ACTIVE",
                "backend": "bedrock",
                "kb_id": self._config.kb_id,
                "status": status,
                "name": kb.get("name", ""),
                "description": kb.get("description", ""),
            }
        except Exception as e:
            return {
                "healthy": False,
                "backend": "bedrock",
                "kb_id": self._config.kb_id,
                "error": str(e),
            }


def _parse_retrieve_response(resp: dict[str, Any]) -> list[SearchResult]:
    """Map Bedrock Retrieve response to SearchResult list."""
    results: list[SearchResult] = []
    for item in resp.get("retrievalResults", []):
        content_obj = item.get("content", {})
        content = content_obj.get("text", "")
        score = item.get("score", 0.0)
        location = item.get("location", {})
        metadata: dict[str, Any] = {}
        if location.get("type"):
            metadata["location_type"] = location["type"]
        s3_loc = location.get("s3Location", {})
        if s3_loc.get("uri"):
            metadata["s3_uri"] = s3_loc["uri"]
        doc_meta = item.get("metadata", {})
        metadata.update(doc_meta)
        doc_id = s3_loc.get("uri", f"bedrock-{len(results)}")
        results.append(SearchResult(
            document_id=doc_id,
            content=content,
            score=score,
            metadata=metadata,
        ))
    return results


def _build_filter(filters: dict[str, Any]) -> dict[str, Any]:
    """Convert simple key=value filters to Bedrock filter format."""
    conditions = []
    for key, value in filters.items():
        conditions.append({
            "equals": {"key": key, "value": value},
        })
    if len(conditions) == 1:
        return conditions[0]
    return {"andAll": conditions}
