"""Chat component renderer — DaisyUI chat bubbles with HTMX.

Renders conversational UI with:
- chat-start (assistant) and chat-end (user) bubbles
- Agent avatar placeholder (gradient circle with initials)
- Message input form with hx-post / hx-target
- Typing indicator (spinner + skeleton lines) via htmx-indicator
- Auto-scroll via MutationObserver on new message append
"""

from __future__ import annotations

from ..models import UIComponent


def render_chat(c: UIComponent) -> str:
    """Render a CHAT component as DaisyUI chat bubble interface."""
    p = c.props
    agent_name = p.get("agent_name", "Agent")
    agent_initials = p.get("agent_initials", agent_name[:2].upper())
    tool = p.get("tool", "")
    post_url = p.get("post_url", "") or (f"/api/chat/{tool}" if tool else "")
    welcome = p.get("welcome_message", f"Hello! I'm {agent_name}. How can I help?")
    cid = f"chat-msgs-{c.id}"
    ind = f"typing-{c.id}"

    avatar = _avatar(agent_initials)
    return (
        f'<div class="flex flex-col h-[480px] rounded-xl border'
        f' border-base-300 bg-base-100 shadow-sm" id="comp-{c.id}">'
        f'<div class="flex-1 overflow-y-auto p-4 space-y-2" id="{cid}">'
        f'{_bubble("start", welcome, avatar=avatar)}'
        f'</div>'
        f'{_typing(agent_name, ind, avatar)}'
        f'{_input_form(post_url, cid, ind)}'
        f'{_scroll_js(cid)}'
        f'</div>'
    )


def render_chat_message(role: str, content: str,
                        agent_initials: str = "AI",
                        is_error: bool = False) -> str:
    """Render a single chat message — called by tool response handler.

    Returns HTML fragment to append to the chat container.
    """
    direction = "start" if role == "assistant" else "end"
    avatar = _avatar(agent_initials) if role == "assistant" else ""
    extra = " chat-bubble-error" if is_error else ""
    return _bubble(direction, content, avatar=avatar, extra_cls=extra)


def _avatar(initials: str) -> str:
    """Gradient circle avatar with agent initials."""
    return (
        '<div class="chat-image avatar placeholder">'
        '<div class="bg-gradient-to-br from-primary to-secondary'
        ' text-primary-content rounded-full w-8">'
        f'<span class="text-xs">{initials}</span>'
        '</div></div>'
    )


def _bubble(direction: str, content: str,
            avatar: str = "", extra_cls: str = "") -> str:
    """Single chat bubble — start (assistant) or end (user)."""
    bg = "bg-base-200 text-base-content" if direction == "start" else ""
    return (
        f'<div class="chat chat-{direction}">'
        f'{avatar}'
        f'<div class="chat-bubble {bg}{extra_cls}">{content}</div>'
        f'</div>'
    )


def _typing(agent_name: str, indicator_id: str, avatar: str) -> str:
    """Typing indicator shown during HTMX requests."""
    return (
        f'<div class="chat chat-start px-4 htmx-indicator"'
        f' id="{indicator_id}">'
        f'{avatar}'
        f'<div class="chat-bubble bg-base-200 text-base-content'
        f' min-w-64"><div class="flex flex-col gap-2">'
        f'<div class="flex items-center gap-2 text-sm opacity-70">'
        f'<span class="loading loading-spinner loading-xs"></span>'
        f'<span>{agent_name} is thinking…</span></div>'
        f'<div class="skeleton h-3 w-full"></div>'
        f'<div class="skeleton h-3 w-4/5"></div>'
        f'<div class="skeleton h-3 w-3/5"></div>'
        f'</div></div></div>'
    )


def _input_form(post_url: str, container_id: str,
                indicator_id: str) -> str:
    """Message input form with HTMX post and auto-scroll."""
    return (
        '<div class="p-3 border-t border-base-300 bg-base-100'
        ' rounded-b-xl">'
        f'<form hx-post="{post_url}" hx-target="#{container_id}"'
        f' hx-swap="beforeend" hx-indicator="#{indicator_id}"'
        f' hx-on::after-request="this.reset()"'
        f' hx-disabled-elt="find button"'
        f' class="flex gap-2">'
        f'<input type="text" name="message"'
        f' class="input input-bordered flex-1"'
        f' placeholder="Type your message…" autocomplete="off"'
        f' required />'
        f'<button type="submit" class="btn btn-primary btn-sm">'
        f'Send</button></form></div>'
    )


def _scroll_js(container_id: str) -> str:
    """MutationObserver to auto-scroll on new child nodes."""
    return (
        f'<script>(function(){{'
        f'const c=document.getElementById("{container_id}");'
        f'if(c){{new MutationObserver(()=>c.scrollTop=c.scrollHeight)'
        f'.observe(c,{{childList:true}})}}'
        f'}})()</script>'
    )
