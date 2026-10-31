import sys

from .server import mcp


def main():
    """Entry point for the CLI."""
    # FastMCP's run implementation handles stdio/sse modes via args usually,
    # but here we expose a simple wrapper primarily for stdio usage.
    mcp.run()


if __name__ == "__main__":
    main()
