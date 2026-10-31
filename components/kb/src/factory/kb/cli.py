import argparse
from factory.kb.server import mcp
from factory.kb.runtime.runtime import KBRuntime


def main():
    parser = argparse.ArgumentParser(description="Knowledge Base Module MCP Server")
    parser.add_argument("command", choices=["run"], help="Command to execute")
    parser.add_argument(
        "--config-dir", required=True, help="Path to configuration directory"
    )

    args = parser.parse_args()

    if args.command == "run":
        # Initialize Runtime
        # We modify the global _runtime in server.py.
        # In a cleaner dependency injection setup we'd pass it, but FastMCP decorators make that tricky without context injection.
        from factory.kb import server as kb_server

        kb_server._runtime = KBRuntime.from_config_dir(args.config_dir)

        # Run MCP Server
        # input/output is handled by FastMCP
        mcp.run()


if __name__ == "__main__":
    main()
