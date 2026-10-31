"""Domain-neutral Workflow composition for workload proxy lifecycle."""
from __future__ import annotations

from typing import Any
import os
from pathlib import Path
import tempfile

from factory.mcp_utils.interface import get_service

from .adapters.authenticated_upstream import AuthenticatedHTTPUpstreamFactory
from .adapters.uds_proxy_host import UvicornUDSProxyHost
from .adapters.workload_proxy import WorkloadProxyActivator
from .workload_lifecycle import WorkloadLifecycleCoordinator


def create_workload_lifecycle(
    *, upstream_factory: Any | None = None, proxy_host: Any | None = None,
) -> WorkloadLifecycleCoordinator:
    """Resolve trusted gateway services and construct the production coordinator."""
    invoker_factory = get_service("tool_invoker_for_caller")
    if not callable(invoker_factory):
        raise RuntimeError("caller-bound tool invoker service is unavailable")
    upstream = upstream_factory or get_service("workload_authenticated_upstream_factory")
    if upstream is None:
        url = os.environ.get("MCP_RESOURCE_SERVER_URL")
        upstream = AuthenticatedHTTPUpstreamFactory(url) if url else None
    host = proxy_host or get_service("workload_proxy_host")
    if host is None:
        root = Path(os.environ.get(
            "WORKLOAD_PROXY_UDS_DIR",
            str(Path(tempfile.gettempdir()) / "companion-x-workloads"),
        ))
        host = UvicornUDSProxyHost(root)
    if not callable(upstream):
        raise RuntimeError("authenticated workload upstream factory is unavailable")
    if host is None or not callable(getattr(host, "mount", None)) \
            or not callable(getattr(host, "unmount", None)):
        raise RuntimeError("workload proxy host service is unavailable")
    invoker = invoker_factory("workflow")
    if not callable(invoker):
        raise RuntimeError("workflow caller-bound invoker is unavailable")
    return WorkloadLifecycleCoordinator(
        invoker, WorkloadProxyActivator(upstream, host))


def resolve_workload_lifecycle() -> WorkloadLifecycleCoordinator | None:
    """Return configured lifecycle support, or None when launch substrate is absent."""
    try:
        return create_workload_lifecycle()
    except RuntimeError:
        return None


__all__ = ["create_workload_lifecycle", "resolve_workload_lifecycle"]
