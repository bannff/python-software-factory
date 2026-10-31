"""Build a squad's LOCAL toolbelt from LangChain's own tool suite.

SDK-first: the squad deploys with the framework's tools, not bespoke ones —
``FileManagementToolkit`` (root-confined file ops), ``ShellTool`` (build/vcs/
ripgrep), and ``DuckDuckGoSearchRun`` (keyless web search, in-container so no
extra hop). ``SquadConfig.toolbelt.tools`` selects which to bind; the file
tools are root-confined to the squad's workspace by the toolkit itself.

Note: ``langchain_community`` is being sunset upstream; it remains the canonical
home for file/shell tools and works against the pinned langchain 1.x stack.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# FileManagementToolkit tool names (root-confined). See langchain_community.
_FILE_TOOLS = {
    "read_file", "write_file", "list_directory", "file_search",
    "copy_file", "move_file", "file_delete",
}
_SHELL = "shell"
_WEB_SEARCH = "web_search"


def available_local_tools() -> list[str]:
    """Return the local tool names a squad toolbelt may request."""
    return sorted(_FILE_TOOLS | {_SHELL, _WEB_SEARCH})


def build_local_toolbelt(tools: list[str], root: str | Path) -> list[Any]:
    """Build LangChain tools for the requested names, bound to ``root``.

    File tools are root-confined by ``FileManagementToolkit``. Unknown names
    are ignored (the runner validates against ``available_local_tools`` first).
    """
    want = set(tools)
    built: list[Any] = []

    file_selection = [name for name in want if name in _FILE_TOOLS]
    if file_selection:
        from langchain_community.agent_toolkits import FileManagementToolkit
        toolkit = FileManagementToolkit(
            root_dir=str(root), selected_tools=file_selection)
        built.extend(toolkit.get_tools())

    if _SHELL in want:
        from langchain_community.tools import ShellTool
        built.append(ShellTool())

    if _WEB_SEARCH in want:
        from langchain_community.tools import DuckDuckGoSearchRun
        built.append(DuckDuckGoSearchRun())

    return built


__all__ = ["available_local_tools", "build_local_toolbelt"]
