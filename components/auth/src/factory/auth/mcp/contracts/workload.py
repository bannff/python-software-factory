"""Private workload credential MCP DTOs."""
from __future__ import annotations

from pydantic import ConfigDict, BaseModel, Field, model_validator

from ...runtime.workload_models import AccessCredential, WorkloadGrant


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class IssueWorkloadCredentialInput(StrictModel):
    workflow_run_id: str = Field(min_length=1, max_length=128)
    attempt_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=0)
    manifest_digest: str
    grant: WorkloadGrant

    @model_validator(mode="after")
    def _manifest_matches(self) -> "IssueWorkloadCredentialInput":
        if self.manifest_digest != self.grant.manifest_digest:
            raise ValueError("attempt and grant manifest digests must match")
        return self


class PrivateIssuedCredential(StrictModel):
    credential: AccessCredential
    access_token: str = Field(min_length=43, max_length=512)


class IssueWorkloadCredentialOutput(StrictModel):
    issued: bool
    duplicate: bool
    credential: PrivateIssuedCredential | None = None
    recovered_credential: AccessCredential | None = None

    @model_validator(mode="after")
    def _one_result(self) -> "IssueWorkloadCredentialOutput":
        if self.issued == self.duplicate:
            raise ValueError("issue result must be either issued or duplicate")
        if self.issued != (self.credential is not None):
            raise ValueError("new issue must contain exactly one private credential")
        if self.duplicate != (self.recovered_credential is not None):
            raise ValueError("duplicate must contain one secret-free credential")
        return self


class RevokeWorkloadCredentialInput(StrictModel):
    workflow_run_id: str = Field(min_length=1, max_length=128)
    attempt_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=0)
    manifest_digest: str
    credential_id: str = Field(min_length=1, max_length=128)


class RevokeWorkloadCredentialOutput(StrictModel):
    revoked: bool


__all__ = [
    "IssueWorkloadCredentialInput", "IssueWorkloadCredentialOutput",
    "PrivateIssuedCredential", "RevokeWorkloadCredentialInput",
    "RevokeWorkloadCredentialOutput",
]
