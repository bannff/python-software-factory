"""Storage ports - abstract interfaces for storage backends."""

from .common import StorageHealth
from .blob import BlobStore, BlobMetadata
from .document import DocumentStore, Document, DocumentWriteResult
from .sql import SQLStore, SQLResult
from .graph import GraphStore, GraphNode, GraphEdge, GraphQueryResult
from .protected_artifacts import BusinessContentArtifactStore
from .credential_slots import (
    CredentialSlotError, CredentialSlotStore, DecryptedSlot, SlotIdentity,
    SlotReceipt,
)
from .owner_secrets import OwnerSecretError, OwnerSecretIdentity, OwnerSecretStore

__all__ = [
    # Common
    "StorageHealth",
    # Blob
    "BlobStore",
    "BlobMetadata",
    # Document
    "DocumentStore",
    "Document",
    "DocumentWriteResult",
    # SQL
    "SQLStore",
    "SQLResult",
    # Graph
    "GraphStore",
    "GraphNode",
    "GraphEdge",
    "GraphQueryResult",
    "BusinessContentArtifactStore",
    # Credential slots (mutable, encrypted, generation-fenced)
    "CredentialSlotStore",
    "CredentialSlotError",
    "SlotIdentity",
    "SlotReceipt",
    "DecryptedSlot",
    # Owner secrets (mutable, encrypted, named KV, no generation fence)
    "OwnerSecretStore",
    "OwnerSecretError",
    "OwnerSecretIdentity",
]
