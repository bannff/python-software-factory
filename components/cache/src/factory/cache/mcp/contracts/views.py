"""Concrete closed DTOs for Cache's declared dashboard view."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import StrictModel


class LayoutOutput(StrictModel):
    type: Literal["flex"]
    direction: Literal["column"]


class MetricProps(StrictModel):
    zone: Literal["info"]
    label: str
    value: str
    icon: str
    tooltip: str
    intent: str | None = None
    data_tool: str | None = None


class FormFieldOutput(StrictModel):
    name: str
    label: str
    type: str
    placeholder: str
    tooltip: str


class FormProps(StrictModel):
    zone: Literal["controls"]
    tool: str
    title: str
    submit_label: str
    fields: list[FormFieldOutput] = Field(max_length=16)


class TabOutput(StrictModel):
    id: str
    label: str
    lazy_tool: str


class TabsProps(StrictModel):
    tabs: list[TabOutput] = Field(max_length=16)


class ActionOutput(StrictModel):
    id: str
    label: str
    icon: str
    tool: str
    submit_label: str
    fields: list[FormFieldOutput] = Field(max_length=16)


class ActionPaneProps(StrictModel):
    actions: list[ActionOutput] = Field(max_length=16)
    default_action: str


class MetricOutput(StrictModel):
    id: str
    type: Literal["metric"]
    props: MetricProps


class FormOutput(StrictModel):
    id: str
    type: Literal["form"]
    props: FormProps


class TabsOutput(StrictModel):
    id: str
    type: Literal["tabs"]
    props: TabsProps


class ActionPaneOutput(StrictModel):
    id: str
    type: Literal["action_pane"]
    props: ActionPaneProps


class PageProps(StrictModel):
    title: str
    subtitle: str
    icon: str
    gradient: str
    tooltip: str


class PageOutput(StrictModel):
    id: str
    type: Literal["page"]
    props: PageProps
    children: list[MetricOutput | FormOutput | TabsOutput | ActionPaneOutput] = Field(max_length=32)


class MetadataOutput(StrictModel):
    description: str
    nav_label: str
    nav_order: int


class CacheViewOutput(StrictModel):
    id: str
    name: str
    brick: str
    icon: str
    layout: LayoutOutput
    components: list[PageOutput] = Field(max_length=8)
    metadata: MetadataOutput


class CacheViewsOutput(StrictModel):
    views: list[CacheViewOutput] = Field(max_length=8)
