"""Executed routes and observed-outcome contracts."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .edge_routing_core import (
    _RoutingValue, _stable_id, _utc_time, RoutingContentRef, RoutingDecisionFeatures,
)


class ExecutedRoute(_RoutingValue):
    """The route actually attempted; other candidates have censored outcomes."""

    candidate_id: str
    selection_propensity: float = Field(gt=0, le=1, allow_inf_nan=False)
    selected_at: datetime
    execution_ref: RoutingContentRef

    @field_validator("candidate_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _stable_id(value)

    @field_validator("selected_at", mode="before")
    @classmethod
    def _time(cls, value: datetime | str) -> datetime:
        return _utc_time(value)
class RoutingReview(_RoutingValue):
    """Human or delegated adjudication of one observed executed outcome."""

    reviewer_ref: str
    adjudication_ref: RoutingContentRef
    reviewed_at: datetime
    verdict: Literal["accepted", "rejected"]

    @field_validator("reviewer_ref")
    @classmethod
    def _reviewer(cls, value: str) -> str:
        return _stable_id(value)

    @field_validator("reviewed_at", mode="before")
    @classmethod
    def _time(cls, value: datetime | str) -> datetime:
        return _utc_time(value)
class RoutingOutcomeEvidence(_RoutingValue):
    """Observed result for the executed route, with run and SDK provenance."""

    outcome_ref: RoutingContentRef
    run_id: str
    sdk_version: str
    provenance_kind: Literal["ditto_sdk_live", "simulated", "imported"]
    observed_at: datetime
    succeeded: bool
    review: RoutingReview | None = None

    @field_validator("run_id", "sdk_version")
    @classmethod
    def _id(cls, value: str) -> str:
        return _stable_id(value)

    @field_validator("observed_at", mode="before")
    @classmethod
    def _time(cls, value: datetime | str) -> datetime:
        return _utc_time(value)

    @model_validator(mode="after")
    def _review_time(self) -> RoutingOutcomeEvidence:
        if self.review is not None and self.review.reviewed_at < self.observed_at:
            raise ValueError("Review cannot precede observed outcome")
        return self
class EdgeRoutingExample(_RoutingValue):
    """One decision snapshot and at most one observed, reviewed route outcome."""

    schema_version: Literal["1.0"]
    record_id: str
    split: Literal["train", "validation", "test"]
    features: RoutingDecisionFeatures
    executed_route: ExecutedRoute | None = None
    outcome: RoutingOutcomeEvidence | None = None

    @field_validator("record_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _stable_id(value)

    @model_validator(mode="after")
    def _route_outcome_order(self) -> EdgeRoutingExample:
        route = self.executed_route
        if route is None:
            if self.outcome is not None:
                raise ValueError("Outcome requires an executed route")
            return self
        if route.candidate_id not in self.features.eligible_candidate_ids:
            raise ValueError("Executed route must select an eligible candidate")
        if route.selected_at < self.features.decision_at:
            raise ValueError("Route execution cannot precede decision")
        selected = next(
            candidate for candidate in self.features.candidates
            if candidate.candidate_id == route.candidate_id
        )
        if route.selected_at >= selected.expires_at:
            raise ValueError("Executed route cannot use an expired capability")
        if self.outcome is not None and self.outcome.observed_at < route.selected_at:
            raise ValueError("Outcome cannot precede route execution")
        return self
