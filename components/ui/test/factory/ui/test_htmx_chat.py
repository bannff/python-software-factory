"""Tests for HTMX chat component renderers.

Verifies correctness properties for the chat bubble UI:
- P2: Chat message direction mapping (user→chat-end, assistant→chat-start)
- P3: Chat component structural completeness (form, hx-post, indicator, scroll, swap)
- P4: Chat message avatar and error styling
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from factory.ui.runtime.adapters.htmx_renderers_chat import render_chat, render_chat_message
from factory.ui.runtime.models import ComponentType, UIComponent


def _chat_component(**overrides) -> UIComponent:
    """Build a CHAT UIComponent with sensible defaults."""
    props = {
        "agent_name": "TestBot", "agent_initials": "TB",
        "post_url": "/api/chat/test_tool", "welcome_message": "Hello!",
    }
    props.update(overrides)
    return UIComponent(id="chat-1", component_type=ComponentType.CHAT, props=props)


# --- P2: Chat message direction mapping ---

class TestChatMessageDirection:

    @given(role=st.sampled_from(["user", "assistant"]), content=st.text(min_size=1))
    @settings(max_examples=50)
    def test_direction_and_content_property(self, role: str, content: str) -> None:
        html = render_chat_message(role, content)
        expected = "chat chat-end" if role == "user" else "chat chat-start"
        assert expected in html
        assert "chat-bubble" in html
        assert content in html


# --- P3: Chat component structural completeness ---

class TestChatStructuralCompleteness:

    def test_form_with_hx_post(self) -> None:
        assert 'hx-post="/api/chat/test_tool"' in render_chat(_chat_component())

    def test_hx_target_references_container(self) -> None:
        html = render_chat(_chat_component())
        assert 'id="chat-msgs-chat-1"' in html
        assert 'hx-target="#chat-msgs-chat-1"' in html

    def test_hx_swap_beforeend(self) -> None:
        assert 'hx-swap="beforeend"' in render_chat(_chat_component())

    def test_htmx_indicator_with_spinner(self) -> None:
        html = render_chat(_chat_component())
        assert "htmx-indicator" in html
        assert "loading-spinner" in html

    def test_scroll_script(self) -> None:
        html = render_chat(_chat_component())
        assert "MutationObserver" in html and "scrollTop" in html

    def test_tool_prop_derives_post_url(self) -> None:
        html = render_chat(_chat_component(post_url="", tool="my_chat"))
        assert 'hx-post="/api/chat/my_chat"' in html

    @given(
        post_url=st.text(min_size=1, max_size=100),
        agent_name=st.text(min_size=1, max_size=30),
    )
    @settings(max_examples=50)
    def test_structural_completeness_property(self, post_url: str, agent_name: str) -> None:
        html = render_chat(_chat_component(post_url=post_url, agent_name=agent_name))
        assert f'hx-post="{post_url}"' in html
        assert "hx-target=" in html
        assert 'hx-swap="beforeend"' in html
        assert "htmx-indicator" in html
        assert "loading-spinner" in html
        assert "<script>" in html


# --- P4: Avatar and error styling ---

class TestChatAvatarAndErrorStyling:

    def test_user_message_has_no_avatar(self) -> None:
        assert "chat-image" not in render_chat_message("user", "Hi", agent_initials="AB")

    def test_non_error_has_no_error_class(self) -> None:
        assert "chat-bubble-error" not in render_chat_message("assistant", "OK")

    def test_error_user_message(self) -> None:
        assert "chat-bubble-error" in render_chat_message("user", "Bad", is_error=True)

    @given(initials=st.text(min_size=1, max_size=4), content=st.text(min_size=1))
    @settings(max_examples=50)
    def test_assistant_avatar_property(self, initials: str, content: str) -> None:
        html = render_chat_message("assistant", content, agent_initials=initials)
        assert "chat-image" in html
        assert initials in html

    @given(content=st.text(min_size=1))
    @settings(max_examples=50)
    def test_error_styling_property(self, content: str) -> None:
        assert "chat-bubble-error" in render_chat_message("assistant", content, is_error=True)
        assert "chat-bubble-error" not in render_chat_message("assistant", content, is_error=False)


# --- Edge cases ---

class TestChatEdgeCases:

    def test_default_initials_from_name(self) -> None:
        c = _chat_component(agent_name="Zephyr")
        del c.props["agent_initials"]
        assert "ZE" in render_chat(c)

    def test_default_welcome_message(self) -> None:
        c = _chat_component(agent_name="Bot")
        del c.props["welcome_message"]
        assert "Bot" in render_chat(c)

    def test_empty_tool_and_post_url(self) -> None:
        assert "<form" in render_chat(_chat_component(post_url="", tool=""))

    def test_unicode_content(self) -> None:
        assert "こんにちは 🎉" in render_chat_message("assistant", "こんにちは 🎉")

    def test_component_id_in_output(self) -> None:
        assert 'id="comp-chat-1"' in render_chat(_chat_component())

    def test_indicator_id_wiring(self) -> None:
        html = render_chat(_chat_component())
        assert 'id="typing-chat-1"' in html
        assert 'hx-indicator="#typing-chat-1"' in html

    def test_input_required_and_form_reset(self) -> None:
        html = render_chat(_chat_component())
        assert "required" in html
        assert "this.reset()" in html

    def test_disabled_elt_on_submit(self) -> None:
        assert "hx-disabled-elt=" in render_chat(_chat_component())
