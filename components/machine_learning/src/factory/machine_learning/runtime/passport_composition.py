"""Server-root composition for ModelPassport store and verifier ports."""
from __future__ import annotations

from pathlib import Path
from factory.mcp_utils.interface import get_service

from .adapters.model_passport_store import LocalModelPassportStore
from .adapters.model_passport_verifier import LocalModelPassportVerifier
from .adapters.passport_conformance import LocalCanModelConformanceRunner
from .model_passport import ModelPassport
from .passport_config import configured_passport_root
from .passport_service import ModelPassportService
from .passport_store_models import ModelPassportPublication, ModelPassportRef


def create_local_passport_service(
    storage_root: str | Path | None = None,
) -> ModelPassportService:
    """Compose production from the mandatory env root; explicit roots are test seams."""
    root = (
        Path(storage_root).expanduser().absolute()
        if storage_root is not None else configured_passport_root()
    )
    invoker = get_service("tool_invoker")
    if invoker is None:
        raise ValueError("tool_invoker unavailable for ModelPassport verification")
    return ModelPassportService(
        store=LocalModelPassportStore(root),
        verifier=LocalModelPassportVerifier(root, invoker),
        conformance_runner=LocalCanModelConformanceRunner(root),
        storage_root=str(root),
    )


def _publish_server_passport(
    passport: ModelPassport, *, storage_root: str | Path,
    service: ModelPassportService | None = None,
) -> ModelPassportPublication:
    """Internal training issuance path; never registered as an MCP tool."""
    target = service or create_local_passport_service(storage_root)
    if passport.promotion_status == "candidate":
        return target.issue_candidate(passport)
    return target.record_rejected(passport)


def get_model_passport(
    *, model_id: str, model_version: str, passport_revision: int,
    uri: str, digest: str, service: ModelPassportService | None = None,
) -> ModelPassport:
    ref = ModelPassportRef(
        model_id=model_id, model_version=model_version,
        passport_revision=passport_revision, uri=uri, digest=digest,
    )
    return (service or create_local_passport_service()).get(ref)


def get_model_passport_by_model(
    model_id: str, model_version: str, passport_revision: int,
    *, service: ModelPassportService | None = None,
) -> ModelPassport:
    return (service or create_local_passport_service()).get_by_model(
        model_id, model_version, passport_revision,
    )


__all__ = [
    "create_local_passport_service", "get_model_passport",
    "get_model_passport_by_model",
]
