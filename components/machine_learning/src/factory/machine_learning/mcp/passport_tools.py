"""Typed MCP surface for exact reads and gated trusted promotion."""
from __future__ import annotations

from typing import Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, authoring, deterministic, fail

from .authoring import _authoring_enabled
from .passport_inference_dtos import (
    ExactPassportInput, PassportByModelInput, PassportOutput,
    PassportPromotionOutput,
)
from ..runtime.passport_composition import create_local_passport_service
from ..runtime.passport_service import ModelPassportService

ServiceFactory = Callable[[], ModelPassportService]


def register(
    mcp: Any, service_factory: ServiceFactory | None = None,
) -> None:
    factory = service_factory or create_local_passport_service

    @mcp.tool(name="ml_get_model_passport")
    @deterministic(input_model=ExactPassportInput, output_model=PassportOutput)
    def get_exact(
        model_id: str, model_version: str, passport_revision: int,
        passport_uri: str, passport_digest: str,
    ) -> ToolResult[PassportOutput]:
        """Read and reverify one passport through its exact registered reference."""
        try:
            ref = ExactPassportInput(
                model_id=model_id, model_version=model_version,
                passport_revision=passport_revision, passport_uri=passport_uri,
                passport_digest=passport_digest,
            ).ref()
            return PassportOutput.model_construct(
                **factory().get(ref).model_dump(mode="python"),
            )
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool(name="ml_verify_and_promote_lightgbm_passport")
    @authoring(
        input_model=ExactPassportInput, output_model=PassportPromotionOutput,
    )
    def verify_and_promote(
        model_id: str, model_version: str, passport_revision: int,
        passport_uri: str, passport_digest: str,
    ) -> ToolResult[PassportPromotionOutput]:
        """Gated isolated verification of one exact registered candidate."""
        if not _authoring_enabled():
            return fail("ML authoring tools are disabled")
        try:
            ref = ExactPassportInput(
                model_id=model_id, model_version=model_version,
                passport_revision=passport_revision, passport_uri=passport_uri,
                passport_digest=passport_digest,
            ).ref()
            publication = factory().verify_and_promote(ref)
            return PassportPromotionOutput.model_construct(
                status=publication.status, ref=publication.ref,
            )
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool(name="ml_verify_and_promote_can_passport")
    @authoring(
        input_model=ExactPassportInput, output_model=PassportPromotionOutput,
    )
    def verify_and_promote_can(
        model_id: str, model_version: str, passport_revision: int,
        passport_uri: str, passport_digest: str,
    ) -> ToolResult[PassportPromotionOutput]:
        """Gated CAN-wide promotion for one exact native candidate."""
        if not _authoring_enabled():
            return fail("ML authoring tools are disabled")
        try:
            ref = ExactPassportInput(
                model_id=model_id, model_version=model_version,
                passport_revision=passport_revision, passport_uri=passport_uri,
                passport_digest=passport_digest,
            ).ref()
            publication = factory().verify_and_promote(ref)
            return PassportPromotionOutput.model_construct(
                status=publication.status, ref=publication.ref,
            )
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool(name="ml_get_model_passport_by_model")
    @deterministic(input_model=PassportByModelInput, output_model=PassportOutput)
    def get_by_model(
        model_id: str, model_version: str, passport_revision: int,
    ) -> ToolResult[PassportOutput]:
        """Read and reverify one configured-store model/version/revision."""
        try:
            value = factory().get_by_model(model_id, model_version, passport_revision)
            return PassportOutput.model_construct(**value.model_dump(mode="python"))
        except Exception as exc:
            return fail(str(exc))


__all__ = ["register"]
