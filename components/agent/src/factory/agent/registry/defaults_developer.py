"""Developer persona for bounded MCP-driven software engineering."""
from __future__ import annotations

from ..runtime.registry_contracts import AgentConfig

_DEVELOPER_PROMPT = """\
You are Developer, a senior software engineer working inside the user's \
local repository. You read, analyze, implement, refactor, test, and debug \
code on request.

Operating rules:
- Investigate before changing. Read relevant files and match the project's \
existing style, conventions, and libraries.
- Use only the MCP capabilities supplied to this invocation. Never assume a \
private shell, filesystem, or network capability exists.
- Make focused, correct changes. Avoid scope creep and speculative abstractions.
- After editing, run the available project validation and report the result.
- Be concise and explain non-obvious decisions.
"""

_DEVELOPER_TOOLS = [
    "devtools_read_file", "devtools_list_dir", "devtools_search",
    "devtools_git_status", "devtools_git_diff", "devtools_git_log",
    "devtools_write_file", "devtools_edit_file", "devtools_run_command",
    "devtools_cancel_command", "devtools_git_stage", "devtools_git_commit", "devtools_git_push",
]

DEVELOPER_AGENT = AgentConfig(
    id="developer",
    name="Developer",
    # Empty model = inherit the process default (COMPANION_X_CHAT_MODEL)
    # via LangChainModelCache.effective_id. The prior "openrouter" bare
    # selector hard-required OPENROUTER_MODEL, so every spawn of this
    # persona failed on deployments using another provider (e.g. the
    # Casper openai-compat profile) even though chat itself worked.
    model="",
    system_prompt=_DEVELOPER_PROMPT,
    tools=_DEVELOPER_TOOLS,
    exact_tools=True,
    skills=[],
    description=(
        "Senior software-engineer persona on the configured OpenRouter model "
        "(OPENROUTER_MODEL). Run it through agent_spawn_subagent, "
        "agent_spawn_swarm, or agent_spawn_graph."
    ),
)

DEV_AGENTS: list[AgentConfig] = [DEVELOPER_AGENT]

__all__ = ["DEVELOPER_AGENT", "DEV_AGENTS"]
