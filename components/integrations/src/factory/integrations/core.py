"""Core types and constants for integrations brick."""

from __future__ import annotations

from enum import Enum
from typing import Literal

SCHEMA_VERSION = 1

ConnectorType = Literal["rest", "graphql", "webhook", "aws"]
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class ConnectorStatus(str, Enum):
    """Status of a connector."""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
