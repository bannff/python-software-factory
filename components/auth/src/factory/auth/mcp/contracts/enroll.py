"""Strict MCP contracts for the OAuth authorization-code enrollment tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class OAuthEnrollBeginInput(_In):
    provider_id: str = Field(min_length=1, max_length=128)
    connection_ref: str = Field(min_length=1, max_length=128)


class OAuthEnrollBeginOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    authorize_url: str
    state: str


class OAuthEnrollCompleteInput(_In):
    state: str = Field(min_length=1, max_length=512)
    code: str = Field(min_length=1, max_length=8192)


class OAuthEnrollCompleteOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: str
    generation: int


__all__ = [
    "OAuthEnrollBeginInput", "OAuthEnrollBeginOutput",
    "OAuthEnrollCompleteInput", "OAuthEnrollCompleteOutput",
]
