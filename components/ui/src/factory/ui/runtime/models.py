"""Domain models for UI components and views."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol


class ComponentType(str, Enum):
    """Built-in UI component types."""
    TEXT = "text"
    CHART = "chart"
    TABLE = "table"
    FORM = "form"
    BUTTON = "button"
    IMAGE = "image"
    CARD = "card"
    LIST = "list"
    LINEAGE = "lineage"
    METRIC = "metric"
    PROGRESS = "progress"
    ALERT = "alert"
    HERO = "hero"
    TABS = "tabs"
    BREADCRUMBS = "breadcrumbs"
    MODAL = "modal"
    TOAST = "toast"
    PAGE = "page"
    ACTION_PANE = "action_pane"
    CODE_BLOCK = "code_block"
    TIMELINE = "timeline"
    STAT_GRID = "stat_grid"
    TREE_VIEW = "tree_view"
    LIVE_FEED = "live_feed"
    COMPOSED_PAGE = "composed_page"
    GRAPH_VIEWER = "graph_viewer"
    CHAT = "chat"
    ITEM_LIST = "item_list"
    STATUS_DOT = "status_dot"
    TREND_BADGE = "trend_badge"
    SPARKLINE = "sparkline"
    DETAIL_PANEL = "detail_panel"
    FILTER_BAR = "filter_bar"
    CUSTOM = "custom"


class ChartType(str, Enum):
    """Chart subtypes."""

    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    AREA = "area"
    SCATTER = "scatter"
    DONUT = "donut"


@dataclass
class ComponentConfig:
    """Configuration for a UI component."""

    component_type: ComponentType
    props: dict[str, Any] = field(default_factory=dict)
    styles: dict[str, str] = field(default_factory=dict)
    children: list["UIComponent"] = field(default_factory=list)


@dataclass
class UIComponent:
    """A renderable UI component."""

    id: str
    component_type: ComponentType
    props: dict[str, Any] = field(default_factory=dict)
    styles: dict[str, str] = field(default_factory=dict)
    children: list["UIComponent"] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.component_type.value,
            "props": self.props,
            "styles": self.styles,
            "children": [c.to_dict() for c in self.children],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIComponent":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            component_type=ComponentType(data["type"]),
            props=data.get("props", {}),
            styles=data.get("styles", {}),
            children=[cls.from_dict(c) for c in data.get("children", [])],
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if "updated_at" in data
            else datetime.now(timezone.utc),
        )


@dataclass
class UIView:
    """A complete view/page containing components."""

    id: str
    name: str
    components: list[UIComponent] = field(default_factory=list)
    layout: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "components": [c.to_dict() for c in self.components],
            "layout": self.layout,
            "metadata": self.metadata,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIView":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            components=[UIComponent.from_dict(c) for c in data.get("components", [])],
            layout=data.get("layout", {}),
            metadata=data.get("metadata", {}),
            version=data.get("version", 1),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if "updated_at" in data
            else datetime.now(timezone.utc),
        )


@dataclass
class ViewUpdate:
    """An update to push to connected clients."""

    view_id: str
    action: str  # "full", "patch", "add_component", "remove_component", "update_component"
    payload: dict[str, Any]
    version: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "view_id": self.view_id,
            "action": self.action,
            "payload": self.payload,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
        }


class ViewStore(Protocol):
    """Protocol for view persistence."""

    def get(self, view_id: str) -> UIView | None: ...
    def save(self, view: UIView) -> None: ...
    def delete(self, view_id: str) -> bool: ...
    def list_views(self) -> list[str]: ...


@dataclass
class SessionState:
    """Session state for memory store (legacy - not currently used)."""

    session_id: str
    data: dict[str, Any] = field(default_factory=dict)
    current_path: str = "/"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
