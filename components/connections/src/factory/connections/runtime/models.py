"""Strict models for owner-registered external MCP servers.

Mirrors the standard ``{"mcpServers": {name: {...}}}`` document so a KiroCrew
or Claude-style config pastes directly. Secrets are never stored: ``env`` and
``headers`` hold ENV-VAR NAMES, resolved inside the API process at dial time
(same rail as ``llm_gateway`` ``api_key_env``). No value can therefore echo
back through list/get, telemetry, logs, or the frontend.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")
_HEADER = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]{1,128}$")
MAX_SERVERS = 64


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ServerSpec(Strict):
    """One server as written in an mcpServers document (secrets by env name)."""

    transport: Literal["stdio", "streamable_http"] = "stdio"
    command: str | None = Field(default=None, min_length=1, max_length=512)
    args: list[str] = Field(default_factory=list)
    cwd: str | None = Field(default=None, min_length=1, max_length=1024)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True

    @model_validator(mode="after")
    def _shape(self) -> "ServerSpec":
        if self.transport == "stdio":
            if not self.command or self.url or self.headers:
                raise ValueError("stdio servers need command and no url/headers")
        elif not self.url or self.command or self.args or self.env or self.cwd:
            raise ValueError("http servers need url and no command/args/env/cwd")
        if len(self.args) > 64 or any(len(item) > 1024 for item in self.args):
            raise ValueError("args too large")
        if len(self.env) > 64 or len(self.headers) > 32:
            raise ValueError("too many env or header entries")
        for key, ref in self.env.items():
            if not _ENV_NAME.fullmatch(key) or not _ENV_NAME.fullmatch(ref):
                raise ValueError("env entries map ENV_NAME -> SOURCE_ENV_NAME")
        for key, ref in self.headers.items():
            if not _HEADER.fullmatch(key) or not _ENV_NAME.fullmatch(ref):
                raise ValueError("header entries map Header-Name -> SOURCE_ENV_NAME")
        if self.url is not None and not self.url.startswith(("http://", "https://")):
            raise ValueError("url must be http(s)")
        return self


class ServerRecord(Strict):
    """Durable owner-scoped server definition with revision CAS."""

    tenant_id: str
    owner_id: str
    name: str
    spec: ServerSpec
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class ServersDocument(Strict):
    """The pasteable ``{"mcpServers": {...}}`` document."""

    mcpServers: dict[str, ServerSpec]

    @model_validator(mode="after")
    def _names(self) -> "ServersDocument":
        if not self.mcpServers or len(self.mcpServers) > MAX_SERVERS:
            raise ValueError(f"1..{MAX_SERVERS} servers required")
        for name in self.mcpServers:
            validate_name(name)
        return self


def validate_name(name: str) -> str:
    if not _NAME.fullmatch(name):
        raise ValueError("server name must match ^[a-z0-9][a-z0-9_-]{0,63}$")
    return name


class StaleServer(RuntimeError):
    """Revision mismatch on a compare-and-swap write."""


__all__ = [
    "MAX_SERVERS", "ServerRecord", "ServerSpec", "ServersDocument", "StaleServer",
    "validate_name",
]
