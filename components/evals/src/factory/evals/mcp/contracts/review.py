"""Strict contracts for Evals-owned development review acceptance."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from factory.mcp_utils.interface import JsonObject

from .durable import RecordRunOutput


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ReviewRow(_Strict):
    evaluator: str = Field(min_length=1, max_length=128)
    score: FiniteFloat = Field(ge=0.0, le=1.0)
    test_pass: bool
    reason: str = Field(min_length=1, max_length=4000)


class ReviewAndRecordInput(_Strict):
    run_id: str = Field(min_length=1, max_length=256)
    policy_id: Literal["review-qa", "review-meta"]
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rows: list[ReviewRow] = Field(min_length=1, max_length=50)
    agent: JsonObject = Field(default_factory=dict)


class ReviewAndRecordOutput(_Strict):
    policy_id: str
    verdict: Literal["PASS", "FAIL"]
    pass_rate: FiniteFloat
    avg_score: FiniteFloat
    record: RecordRunOutput


__all__ = ["ReviewAndRecordInput", "ReviewAndRecordOutput", "ReviewRow"]
