"""Core types and constants for sandbox component."""

from enum import Enum
from typing import Any

COMPONENT_NAME = "sandbox"
COMPONENT_VERSION = "0.1.0"


class EnvironmentStatus(str, Enum):
    """Environment lifecycle status."""
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPING = "stopping"
    TERMINATED = "terminated"
    ERROR = "error"
    UNKNOWN = "unknown"


class InstanceType(str, Enum):
    """Common EC2 instance types."""
    T3_MICRO = "t3.micro"
    T3_SMALL = "t3.small"
    T3_MEDIUM = "t3.medium"
    M5_LARGE = "m5.large"


SUPPORTED_ADAPTERS = ["mock", "docker", "aws_ec2", "aws_ssm"]


DEFAULT_CONFIG: dict[str, Any] = {
    "instance_type": "t3.micro",
    "timeout_seconds": 3600,
    "auto_terminate": True,
}
