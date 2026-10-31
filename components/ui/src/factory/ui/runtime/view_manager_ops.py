"""View manager component operations."""

from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from .models import UIComponent, ViewUpdate

if TYPE_CHECKING:
    from .view_manager import ViewManager


def _utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class ViewComponentOps:
    """Component operations for ViewManager."""

    def __init__(self, manager: "ViewManager"):
        self._manager = manager

    async def add_component(self, view_id: str, component: UIComponent, position: int | None = None):
        view = self._manager.store.get(view_id)
        if not view:
            return None
        if position is not None:
            view.components.insert(position, component)
        else:
            view.components.append(component)
        view.updated_at = _utcnow()
        self._manager.store.save(view)
        update = ViewUpdate(
            view_id=view_id, action="add_component",
            payload={"component": component.to_dict(), "position": position},
            version=view.version,
        )
        self._manager.store.record_update(update)
        await self._manager.push_channel.push(update)
        return view

    async def update_component(
        self, view_id: str, component_id: str,
        props: dict[str, Any] | None = None, styles: dict[str, str] | None = None,
    ):
        view = self._manager.store.get(view_id)
        if not view:
            return None
        component = next((c for c in view.components if c.id == component_id), None)
        if not component:
            return None
        if props:
            component.props.update(props)
        if styles:
            component.styles.update(styles)
        component.updated_at = _utcnow()
        view.updated_at = _utcnow()
        self._manager.store.save(view)
        update = ViewUpdate(
            view_id=view_id, action="update_component",
            payload={"component_id": component_id, "props": props, "styles": styles},
            version=view.version,
        )
        self._manager.store.record_update(update)
        await self._manager.push_channel.push(update)
        return component

    async def remove_component(self, view_id: str, component_id: str) -> bool:
        view = self._manager.store.get(view_id)
        if not view:
            return False
        original_len = len(view.components)
        view.components = [c for c in view.components if c.id != component_id]
        if len(view.components) == original_len:
            return False
        view.updated_at = _utcnow()
        self._manager.store.save(view)
        update = ViewUpdate(
            view_id=view_id, action="remove_component",
            payload={"component_id": component_id}, version=view.version,
        )
        self._manager.store.record_update(update)
        await self._manager.push_channel.push(update)
        return True

    async def push_view(self, view_id: str) -> int:
        view = self._manager.store.get(view_id)
        if not view:
            return 0
        update = ViewUpdate(
            view_id=view_id, action="full",
            payload=view.to_dict(), version=view.version,
        )
        self._manager.store.record_update(update)
        return await self._manager.push_channel.push(update)
