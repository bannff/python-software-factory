import argparse
import os

from .server import mcp


def main():
    parser = argparse.ArgumentParser(description="Run the UI Module MCP Server")
    parser.add_argument("command", choices=["run", "inspect"], help="Command to execute")
    parser.add_argument("--config-dir", default="./config", help="Path to configuration directory")

    args = parser.parse_args()

    # Set config dir in environment for the server to pick up
    os.environ["UI_CONFIG_DIR"] = os.path.abspath(args.config_dir)

    if args.command == "run":
        # In a real FastMCP app, we might use mcp.run() directly or uvicorn
        # For this skeleton, we delegate to FastMCP's run logic or simple print
        print(f"Starting UI Module MCP Server with config: {os.environ['UI_CONFIG_DIR']}")
        mcp.run()
    elif args.command == "inspect":
        print("Inspection not implemented in this skeleton.")


if __name__ == "__main__":
    main()
