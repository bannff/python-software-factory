"""UI Module runtime exports."""

from .adapters import (
    JsonAdapter,
    InlineHtmlRenderAdapter,
    RenderAdapter,
    RenderResult,
    A2UIAdapter,
    A2UIConfig,
    create_a2ui_adapter,
)
from .config import ConfigLoader, UISettings, ViewDefinition
from .envelope import ContextEnvelope
from .models import (
    ChartType,
    ComponentConfig,
    ComponentType,
    UIComponent,
    UIView,
    ViewStore,
    ViewUpdate,
)
from .push_channel import ChannelType, ClientConnection, PushChannel
from .registry import ComponentDefinition, ComponentRegistry
from .runtime import UIRuntime, get_runtime, reset_runtime
from .store.view_store import InMemoryViewStore
from .view_manager import ViewManager

# A2UI exports
from . import a2ui

__all__ = [
    # Models
    "ComponentType",
    "ChartType",
    "ComponentConfig",
    "UIComponent",
    "UIView",
    "ViewUpdate",
    "ViewStore",
    # Envelope
    "ContextEnvelope",
    # Config
    "ConfigLoader",
    "UISettings",
    "ViewDefinition",
    # Registry
    "ComponentRegistry",
    "ComponentDefinition",
    # Store
    "InMemoryViewStore",
    # Push
    "PushChannel",
    "ClientConnection",
    "ChannelType",
    # Manager
    "ViewManager",
    # Runtime
    "UIRuntime",
    "get_runtime",
    "reset_runtime",
    # Adapters
    "RenderAdapter",
    "RenderResult",
    "JsonAdapter",
    "InlineHtmlRenderAdapter",
    "A2UIAdapter",
    "A2UIConfig",
    "create_a2ui_adapter",
    # A2UI
    "a2ui",
]
