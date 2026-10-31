"""REST API adapter using FastAPI."""

from __future__ import annotations

import logging
from typing import Any, Callable

from ...core import APIHealth, RouteInfo

logger = logging.getLogger(__name__)


class RESTAdapter:
    """REST API adapter using FastAPI."""

    def __init__(self) -> None:
        try:
            from fastapi import FastAPI
            self._mcp_app = None
            self._app = FastAPI(title="Factory API", version="1.0.0")
            self._install_cors()
            self._register_mcp_bridge()
            self._rewire_lifespan()
            from ..background_tasks import install_runtime_lifespan
            install_runtime_lifespan(self._app)
        except ImportError:
            self._app = None
            self._mcp_app = None
        self._routes: list[RouteInfo] = []

    def _install_cors(self) -> None:
        """Apply the shared CORS policy to the whole app (incl. the /mcp mount).

        Starlette middleware wraps the router, so this also covers the mounted
        MCP Streamable-HTTP sub-app and answers its OPTIONS preflight — the
        single fix that lets browser clients (the dashboard :3000)
        complete the cross-origin MCP handshake. Replaces the retired per-route
        ``_CORS_HEADERS``. bd:python-factory-iqm3h.
        """
        if self._app is None:
            return
        try:
            from starlette.middleware.cors import CORSMiddleware
            from factory.mcp_utils.interface import cors_options
            self._app.add_middleware(CORSMiddleware, **cors_options())
            logger.info("CORS middleware installed")
        except Exception as e:
            logger.warning("CORS middleware install failed: %s", e)

    def _register_mcp_bridge(self) -> None:
        """Wire MCP gateway routes into the FastAPI app."""
        if self._app is None:
            return
        try:
            from ..bridge import register_bridge_routes
            register_bridge_routes(self._app)
            logger.info("MCP gateway bridge routes registered")
        except Exception as e:
            logger.warning("MCP bridge unavailable: %s", e)

        try:
            from ..ag_ui_routes import register_ag_ui_routes
            register_ag_ui_routes(self._app)
            logger.info("AG-UI SSE routes registered")
        except Exception as e:
            logger.warning("AG-UI routes unavailable: %s", e)

        try:
            from ..events_sse import register_events_sse_routes
            register_events_sse_routes(self._app)
            logger.info("Tool-stream SSE routes registered")
        except Exception as e:
            logger.warning("Tool-stream SSE routes unavailable: %s", e)

        try:
            from ..run_stream_routes import register_run_stream_routes
            register_run_stream_routes(self._app)
            logger.info("Per-run SSE stream routes registered")
        except Exception as e:
            logger.warning("Per-run SSE stream routes unavailable: %s", e)

        try:
            from ..terminal_completion_routes import register_terminal_completion_routes
            from ..terminal_ws_routes import register_terminal_routes
            register_terminal_routes(self._app)
            register_terminal_completion_routes(self._app)
            logger.info("Terminal PTY HTTP/WebSocket/completion routes registered")
        except Exception as e:
            logger.warning("Terminal PTY routes unavailable: %s", e)

        try:
            from ..oauth_routes import register_oauth_routes
            register_oauth_routes(self._app)
            logger.info("OAuth callback route registered")
        except Exception as e:
            logger.warning("OAuth callback route unavailable: %s", e)

        try:
            from ..side_chat_wiring import register_side_chat
            register_side_chat(self._app)
            logger.info("Side chat routes registered")
        except Exception as e:
            logger.warning("Side chat routes unavailable: %s", e)

        self._mount_mcp_endpoint()

    def _mount_mcp_endpoint(self) -> None:
        """Mount MCP aggregator as Streamable HTTP at /mcp."""
        if self._app is None:
            return
        try:
            from ..bridge import _get_aggregator
            agg = _get_aggregator()
            if agg is None:
                return
            server = getattr(agg, "mcp", None)
            if server is None:
                return
            if hasattr(server, "http_app"):
                self._mcp_app = server.http_app(path="/", stateless_http=True)
            else:
                from factory.mcp_server.interface import build_streamable_http_app
                self._mcp_app = build_streamable_http_app(server)
            self._app.mount("/mcp", self._mcp_app)
            logger.info("MCP Streamable HTTP mounted at /mcp")
        except Exception as e:
            logger.warning("MCP endpoint mount failed: %s", e)

    def _rewire_lifespan(self) -> None:
        """Compose MCP sub-app lifespan into the parent FastAPI app."""
        if self._app is None or self._mcp_app is None:
            return
        try:
            from contextlib import asynccontextmanager

            original = self._app.router.lifespan_context
            child = self._mcp_app.router.lifespan_context

            @asynccontextmanager
            async def combined(app: Any):
                async with original(app):
                    async with child(self._mcp_app):
                        yield

            self._app.router.lifespan_context = combined
            logger.info("MCP lifespan composed into FastAPI app")
        except Exception as e:
            logger.warning("MCP lifespan composition failed: %s", e)

    @property
    def adapter_type(self) -> str:
        """Return adapter type identifier."""
        return "rest"

    def add_route(
        self,
        path: str,
        method: str,
        handler: Callable[..., Any],
        tags: list[str] | None = None,
    ) -> None:
        """Register a route with FastAPI."""
        if self._app is None:
            raise RuntimeError("FastAPI not available")

        route_info = RouteInfo(
            path=path,
            method=method.upper(),
            handler=handler.__name__,
            tags=tags or [],
        )
        self._routes.append(route_info)

        # Register with FastAPI
        self._app.add_api_route(
            path,
            handler,
            methods=[method.upper()],
            tags=tags,
        )

    def list_routes(self) -> list[RouteInfo]:
        """List all registered routes."""
        return self._routes.copy()

    def get_app(self) -> Any:
        """Get the FastAPI application."""
        return self._app

    def health_check(self) -> APIHealth:
        """Check adapter health."""
        return APIHealth(
            healthy=self._app is not None,
            adapter="rest",
            routes_count=len(self._routes),
            error=None if self._app else "FastAPI not available",
        )
