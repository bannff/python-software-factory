"""Validated peer-mesh settings for isolated Sandbox Docker environments."""
from __future__ import annotations

import re
from typing import Any

from pydantic import (
    BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator,
)


_NETWORK_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,46}[a-z0-9])?$")
_DNS_ALIAS = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class PeerNetworkSpec(BaseModel):
    """A stable alias and listener port on a Sandbox-owned Docker bridge."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)

    network_id: str = Field(min_length=1, max_length=48)
    alias: str = Field(min_length=1, max_length=63)
    port: StrictInt = Field(gt=0, le=65535)
    internal: StrictBool = False

    @field_validator("network_id")
    @classmethod
    def valid_network_id(cls, value: str) -> str:
        if not _NETWORK_ID.fullmatch(value):
            raise ValueError("network_id must be a lowercase DNS slug")
        return value

    @field_validator("alias")
    @classmethod
    def valid_alias(cls, value: str) -> str:
        if not _DNS_ALIAS.fullmatch(value):
            raise ValueError("alias must be a lowercase DNS name")
        return value

    @property
    def docker_network_name(self) -> str:
        return f"factory-sandbox-{self.network_id}"

    @property
    def endpoint(self) -> str:
        return f"{self.alias}:{self.port}"

    def public_metadata(self) -> dict[str, str | int | bool]:
        return {
            "network_id": self.network_id,
            "network_name": self.docker_network_name,
            "alias": self.alias,
            "port": self.port,
            "internal": self.internal,
            "endpoint": self.endpoint,
        }


def validate_peer_network(value: Any) -> PeerNetworkSpec | None:
    """Validate untrusted adapter config before Docker can mutate resources."""
    if value is None:
        return None
    if isinstance(value, PeerNetworkSpec):
        return value
    return PeerNetworkSpec.model_validate(value)
