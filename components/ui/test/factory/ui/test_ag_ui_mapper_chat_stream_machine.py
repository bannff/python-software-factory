"""``RuleBasedStateMachine`` driving the chat-stream mapper.

Stateful Hypothesis testing — invariants are checked after every rule
fires, so any sequence the engine can construct that violates the AG-UI
contract becomes a falsifying example.

Lives in a sibling module to ``test_ag_ui_mapper_chat_stream.py`` so
each test file stays under the 200 LOC cap.
"""
from __future__ import annotations

from typing import Any

from hypothesis import HealthCheck, settings, strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine, initialize, invariant, rule,
)

from factory.agent.runtime.models import (
    DoneEvent, ReasoningTextEvent, TextDeltaEvent,
    ToolCallDeltaEvent, ToolResultEvent,
)
from factory.ui.runtime.ag_ui_mapper_chat import (
    AGUIStreamState, map_chat_stream_event,
)

from ._ag_ui_mapper_invariants import check_invariants


class _ChatMapperMachine(RuleBasedStateMachine):
    """Drive the mapper with random events; invariants are checked at every step."""

    def __init__(self) -> None:
        super().__init__()
        self.state = AGUIStreamState()
        self.events: list[dict[str, Any]] = []
        self._open_tools: set[str] = set()

    @initialize()
    def _setup(self) -> None:
        self.state = AGUIStreamState()
        self.events = []
        self._open_tools = set()

    @rule(content=st.text(min_size=0, max_size=10),
          mid=st.sampled_from(["m1", "m2"]))
    def text_delta(self, content: str, mid: str) -> None:
        if self.state.terminated:
            return
        self.events.extend(map_chat_stream_event(
            TextDeltaEvent(content=content, message_id=mid), self.state,
        ))

    @rule(tcid=st.sampled_from(["tc1", "tc2"]),
          name=st.sampled_from(["kb", "evals", None]))
    def tool_call_delta(self, tcid: str, name: str | None) -> None:
        if self.state.terminated:
            return
        self._open_tools.add(tcid)
        self.events.extend(map_chat_stream_event(
            ToolCallDeltaEvent(
                tool_call_id=tcid, tool_name=name, args_delta="",
            ), self.state,
        ))

    @rule(tcid=st.sampled_from(["tc1", "tc2"]))
    def tool_result(self, tcid: str) -> None:
        if self.state.terminated or tcid not in self._open_tools:
            return
        self.events.extend(map_chat_stream_event(
            ToolResultEvent(tool_call_id=tcid,
                             payload={"ok": True}), self.state,
        ))

    @rule()
    def reasoning(self) -> None:
        if self.state.terminated:
            return
        self.events.extend(map_chat_stream_event(
            ReasoningTextEvent(content="think"), self.state,
        ))

    @rule()
    def finish_run(self) -> None:
        if self.state.terminated:
            return
        self.events.extend(map_chat_stream_event(
            DoneEvent(reason="stop"), self.state,
        ))

    @invariant()
    def invariants_hold(self) -> None:
        # Mid-run: messages may still be open.
        check_invariants(self.events, require_closure=False)

    @invariant()
    def all_tcids_closed_after_terminal(self) -> None:
        # bd:python-factory-lmne — after DoneEvent or ErrorEvent every
        # opened tool_call_id must also be in result_emitted_tcids
        # (either via tool_result or via _synth_unclosed_tool_ends).
        if not self.state.terminated:
            return
        assert (self.state.seen_tool_call_ids
                <= self.state.result_emitted_tcids), (
            "Unclosed tool_call_ids after stream finalize: "
            f"{self.state.seen_tool_call_ids - self.state.result_emitted_tcids}"
        )


TestChatMapperMachine = _ChatMapperMachine.TestCase
TestChatMapperMachine.settings = settings(
    max_examples=50, deadline=None,
    suppress_health_check=[HealthCheck.too_slow,
                            HealthCheck.filter_too_much],
)
