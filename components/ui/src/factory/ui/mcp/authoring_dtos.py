"""Strict typed boundaries for UI authoring MCP tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AuthoringStatusInput(_Input):
    pass


class CreateViewInput(_Input):
    name: str
    view_id: str | None = None
    layout_type: str = "flex"
    layout_columns: int = 1
    envelope: dict[str, Any] | None = None


class DeleteViewInput(_Input):
    view_id: str
    envelope: dict[str, Any] | None = None


class AddComponentInput(_Input):
    view_id: str
    component_type: str
    props: dict[str, Any] | None = None
    styles: dict[str, str] | None = None
    component_id: str | None = None
    position: int | None = None
    envelope: dict[str, Any] | None = None


class UpdateComponentInput(_Input):
    view_id: str
    component_id: str
    props: dict[str, Any] | None = None
    styles: dict[str, str] | None = None
    envelope: dict[str, Any] | None = None


class RemoveComponentInput(_Input):
    view_id: str
    component_id: str
    envelope: dict[str, Any] | None = None


class PushViewInput(_Input):
    view_id: str
    envelope: dict[str, Any] | None = None


class CreateDashboardInput(_Input):
    name: str
    metrics: list[dict[str, Any]] | None = None
    charts: list[dict[str, Any]] | None = None
    tables: list[dict[str, Any]] | None = None
    envelope: dict[str, Any] | None = None


class AuthoringStatusOutput(_Output):
    enabled: bool
    config_dir: str
    views_dir: str
    schema_version: str


class CreateViewOutput(_Output):
    created: bool
    view: dict[str, Any]
    request_id: str | None = None


class DeleteViewOutput(_Output):
    deleted: bool
    view_id: str
    request_id: str | None = None


class AddComponentOutput(_Output):
    added: bool
    component: dict[str, Any]
    request_id: str | None = None


class UpdateComponentOutput(_Output):
    updated: bool
    component: dict[str, Any]
    request_id: str | None = None


class RemoveComponentOutput(_Output):
    removed: bool
    component_id: str
    request_id: str | None = None


class PushViewOutput(_Output):
    pushed: bool
    view_id: str
    recipients: int
    request_id: str | None = None


class CreateDashboardOutput(_Output):
    created: bool
    view_id: str
    request_id: str | None = None
