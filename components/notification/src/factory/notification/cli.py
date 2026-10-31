import argparse
import asyncio
import os

import yaml
from .server import mcp, dispatcher


def load_settings(config_dir: str) -> dict:
    settings_path = os.path.join(config_dir, "settings.yaml")
    if not os.path.exists(settings_path):
        # Default settings if file missing
        return {"backend": {"type": "stdio"}}

    with open(settings_path, "r") as f:
        return yaml.safe_load(f)


async def run_server(config_dir: str):
    settings = load_settings(config_dir)
    await dispatcher.initialize(config_dir, settings)
    # Run FastMCP
    await mcp.run_stdio_async()


def main():
    parser = argparse.ArgumentParser(description="Notification Module MCP Server")
    parser.add_argument("command", choices=["run"], help="Command to execute")
    parser.add_argument(
        "--config-dir", default="./config", help="Path to config directory"
    )

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(run_server(args.config_dir))


if __name__ == "__main__":
    main()
