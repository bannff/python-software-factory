"""Polylith Interface for auth module."""

from .server import create_mcp_server as create_server
from .runtime.runtime import AuthRuntime as Runtime
from .access import CredentialVerifierPort, create_credential_verifier
from .runtime.ports import WorkloadCredentialProvider, WorkloadGrantPolicyPort
from .runtime.workload_credentials import (
    LocalOpaqueWorkloadCredentialProvider, WorkloadCredentialConflict,
)
from .runtime.workload_models import (
    AccessCredential, IssuedWorkloadCredential, WorkloadGrant,
    canonical_grant_manifest_digest,
)

__all__ = [
    "AccessCredential", "CredentialVerifierPort", "IssuedWorkloadCredential",
    "LocalOpaqueWorkloadCredentialProvider", "Runtime", "WorkloadCredentialProvider",
    "WorkloadGrantPolicyPort",
    "WorkloadCredentialConflict", "WorkloadGrant",
    "canonical_grant_manifest_digest", "create_credential_verifier", "create_server",
]
