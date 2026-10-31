"""DTOs for immutable Storage document writes."""
from __future__ import annotations

from typing import Literal

from .base import DTO, JsonObject


class DocCreateOrMatchInput(DTO):
    collection: str
    doc_id: str
    data: JsonObject
    content_hash: str


class DocCreateOrMatchOutput(DTO):
    status: Literal["created", "matched", "conflict", "unsupported"]
    id: str
    collection: str
    content_hash: str
    existing_content_hash: str = ""
