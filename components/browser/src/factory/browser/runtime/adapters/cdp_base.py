"""CDP adapter base - connection and command handling."""

import asyncio
import json
import uuid
from typing import Any

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


class CDPBase:
    """Base class for CDP connection management."""

    def __init__(self, chrome_path: str | None = None, port: int = 9222) -> None:
        """Initialize CDP base."""
        self._chrome_path = chrome_path or self._find_chrome()
        self._port = port
        self._sessions: dict[str, dict[str, Any]] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    @property
    def chrome_path(self) -> str:
        """Public accessor for the resolved Chrome/Chromium candidate."""
        return self._chrome_path

    def _find_chrome(self) -> str:
        """Find Chrome/Chromium executable."""
        import shutil
        candidates = [
            "google-chrome", "chromium", "chromium-browser",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
        for candidate in candidates:
            if shutil.which(candidate):
                return candidate
        return "chromium"

    async def launch(self, config: dict[str, Any]) -> str:
        """Launch Chrome with CDP enabled."""
        if not HAS_WEBSOCKETS:
            raise RuntimeError("websockets package required for CDP adapter")

        session_id = str(uuid.uuid4())
        port = self._port + len(self._sessions)
        
        args = [self._chrome_path, f"--remote-debugging-port={port}",
                "--no-first-run", "--no-default-browser-check"]
        if config.get("headless", True):
            args.append("--headless=new")
        if config.get("user_agent"):
            args.append(f"--user-agent={config['user_agent']}")

        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        self._processes[session_id] = process
        await asyncio.sleep(1)
        
        ws_url = await self._get_ws_url(port)
        self._sessions[session_id] = {"port": port, "ws_url": ws_url, "config": config, "msg_id": 0}
        return session_id

    async def _get_ws_url(self, port: int) -> str:
        """Get WebSocket URL from CDP endpoint."""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://localhost:{port}/json/version")
            return resp.json()["webSocketDebuggerUrl"]

    async def _send_command(
        self, session_id: str, method: str, params: dict[str, Any] | None = None
    ) -> Any:
        """Send CDP command and get response."""
        session = self._sessions[session_id]
        session["msg_id"] += 1
        msg_id = session["msg_id"]
        message = {"id": msg_id, "method": method, "params": params or {}}
        
        async with websockets.connect(session["ws_url"]) as ws:
            await ws.send(json.dumps(message))
            while True:
                response = json.loads(await ws.recv())
                if response.get("id") == msg_id:
                    if "error" in response:
                        raise RuntimeError(response["error"]["message"])
                    return response.get("result", {})

    async def close(self, session_id: str) -> None:
        """Close browser session."""
        if session_id in self._processes:
            self._processes[session_id].terminate()
            await self._processes[session_id].wait()
            del self._processes[session_id]
        self._sessions.pop(session_id, None)

    def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        return {"healthy": HAS_WEBSOCKETS, "adapter": "cdp", "sessions": len(self._sessions)}
