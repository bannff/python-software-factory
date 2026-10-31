"""APIGenMT stage: LLM-powered semantic tool injection.

Ported from bannff/Agentic-Datasets@26cb683 (``stages/apigenmt_v2.py``).
Uses LLM reasoning to identify where tool calls genuinely help and injects
them following the APIGen methodology. Pure logic — completions arrive
through the ``CompletionPort`` protocol.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Iterator
from typing import Any

from ..ports import CompletionPort
from ..records import ConversationRecord, Message, ToolCall
from ._prompts_apigenmt import APIGENMT_ANALYZE, APIGENMT_GENERATE_RESPONSE, APIGENMT_SYSTEM
from ._shared import StageDefaults, model_of, parse_json_object, require_completion

logger = logging.getLogger(__name__)


def _format_conversation(messages: list[Message]) -> str:
    """Format messages (with indices) for inclusion in prompts."""
    return "\n".join(f"[{i}] {msg.role.upper()}: {msg.content}" for i, msg in enumerate(messages))


def _format_tools_catalog(tools: list[dict[str, Any]]) -> str:
    """Format tools catalog for inclusion in prompts."""
    lines: list[str] = []
    for tool in tools:
        lines.append(f"- {tool.get('name', 'unknown')}: {tool.get('description', '')}")
        for pname, pinfo in (tool.get("parameters") or {}).items():
            ptype = pinfo.get("type", "string")
            required = " (required)" if pinfo.get("required") else ""
            lines.append(f"    {pname}: {ptype}{required}")
    return "\n".join(lines)


def _analyze_for_tools(
    messages: list[Message], tools: list[dict[str, Any]], completion: CompletionPort
) -> list[dict[str, Any]]:
    """Use the LLM to identify tool injection points."""
    prompt = APIGENMT_ANALYZE.format(
        conversation=_format_conversation(messages), tools=_format_tools_catalog(tools)
    )
    try:
        response = completion.get_completion(
            prompt,
            system_prompt=APIGENMT_SYSTEM,
            temperature=StageDefaults.TEMPERATURE_FOCUSED,  # Lower for consistent analysis
            max_tokens=StageDefaults.MAX_TOKENS_LONG,
        )
        analysis = parse_json_object(response, required_key="tool_calls")
        if analysis:
            return analysis["tool_calls"]
        logger.warning("Failed to parse tool analysis response")
        return []
    except Exception as error:
        logger.warning("Tool analysis failed: %s", error)
        return []


def _generate_tool_response(
    tool_name: str, arguments: dict[str, Any], tool_desc: str, completion: CompletionPort
) -> str:
    """Generate a realistic tool response using the LLM."""
    prompt = APIGENMT_GENERATE_RESPONSE.format(
        tool_name=tool_name, arguments=json.dumps(arguments), description=tool_desc
    )
    try:
        return completion.get_completion(
            prompt, temperature=0.6, max_tokens=StageDefaults.MAX_TOKENS_MEDIUM
        ).strip()
    except Exception as error:
        logger.warning("Tool response generation failed: %s", error)
        return f"[{tool_name} result for {arguments}]"


def _passthrough(rec: ConversationRecord, **extra: Any) -> ConversationRecord:
    meta: dict[str, Any] = dict(rec.metadata or {})
    meta.update({"stage": "apigenmt", "agentic": False, **extra})
    return ConversationRecord(messages=rec.messages, metadata=meta, source=rec.source, id=rec.id)


def _inject_tools(
    rec: ConversationRecord,
    spec_list: list[dict[str, Any]],
    tool_descs: dict[str, str],
    generate_responses: bool,
    completion: CompletionPort,
) -> tuple[list[Message], int]:
    """Insert tool calls and responses; returns (messages, injected_count)."""
    new_messages: list[Message] = list(rec.messages)
    injected_count = 0
    # Sort by index descending to insert from end (prevents index shift issues)
    spec_list.sort(key=lambda x: x.get("after_message_index", 0), reverse=True)
    for spec in spec_list:
        idx: int = spec.get("after_message_index", 0)
        tool_name: str = spec.get("tool_name", "")
        arguments: dict[str, Any] = spec.get("arguments", {})
        if idx < 0 or idx >= len(new_messages):
            continue
        msg = new_messages[idx]
        if msg.role != "assistant":
            continue
        tool_call = ToolCall(
            id=f"tc_{rec.id}_{injected_count}", name=tool_name,
            arguments=arguments, status="completed",
        )
        existing_calls = [*(msg.tool_calls or []), tool_call]
        new_messages[idx] = Message(
            role=msg.role, content=msg.content, metadata=msg.metadata, tool_calls=existing_calls
        )
        if generate_responses:
            content = _generate_tool_response(
                tool_name, arguments, tool_descs.get(tool_name, ""), completion
            )
        else:
            content = f"[{tool_name} result]"
        new_messages.insert(
            idx + 1,
            Message(role="tool", content=content, tool_name=tool_name, tool_call_id=tool_call.id),
        )
        injected_count += 1
    return new_messages, injected_count


def apigenmt(
    records: Iterable[ConversationRecord],
    *,
    tools: list[dict[str, Any]] | None = None,
    max_tools_per_conversation: int = 3,
    use_llm: bool = True,
    generate_responses: bool = True,
    completion: CompletionPort | None = None,
) -> Iterator[ConversationRecord]:
    """Inject tool calls into conversations using LLM semantic analysis."""
    if not tools:
        logger.info("APIGenMT: No tools configured, passing through")
        for rec in records:
            yield _passthrough(rec)
        return

    if use_llm:
        completion = require_completion(completion, "apigenmt")
    tool_descs = {t.get("name", ""): t.get("description", "") for t in tools}
    logger.info("APIGenMT: %s tools, use_llm=%s", len(tools), use_llm)

    for rec in records:
        if not use_llm:
            yield _passthrough(rec, via="disabled")
            continue
        try:
            spec_list = _analyze_for_tools(rec.messages, tools, completion)
            if not spec_list:
                yield _passthrough(rec, via="llm_no_tools")
                continue
            spec_list = spec_list[:max_tools_per_conversation]
            new_messages, injected_count = _inject_tools(
                rec, spec_list, tool_descs, generate_responses, completion
            )
            meta: dict[str, Any] = dict(rec.metadata or {})
            meta.update({
                "stage": "apigenmt",
                "agentic": True,
                "via": "llm",
                "model": model_of(completion),
                "tools_injected": injected_count,
            })
            yield ConversationRecord(
                messages=new_messages, metadata=meta, source=rec.source, id=rec.id
            )
        except Exception as error:
            logger.warning("APIGenMT failed for %s: %s", rec.id, error)
            yield _passthrough(rec, via="error")
