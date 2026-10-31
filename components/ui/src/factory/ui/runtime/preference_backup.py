"""Row 102 (feature-map) — host-side backup/restore of the owner's durable
UI preferences, so they survive a moved dashboard port or a relocated
Electron ``userData`` (upstream's own framing for this row).

Composes the EXISTING ``ChatPreferenceStore.update``/``update_display``
calls rather than adding a new store primitive: every real, durable
preference field (chat/display/shortcuts/memory-mode) is already covered
by those two calls together, so a full "export everything, restore
everything" round trip needs no new mutation surface — just an ordered
pair of calls using the record's own current revision at each step.
"""
from __future__ import annotations

from .chat_preferences import ChatPreferenceStore, ChatPreferences


def export_preferences(store: ChatPreferenceStore, tenant_id: str, owner_id: str) -> ChatPreferences:
    """Read the complete durable preference record for one owner."""
    return store.get(tenant_id, owner_id)


def restore_preferences(
    store: ChatPreferenceStore, tenant_id: str, owner_id: str, snapshot: ChatPreferences,
) -> ChatPreferences:
    """Overwrite the CURRENT record with every field from ``snapshot``.

    Two sequential CAS writes (chat-shaped fields, then display-shaped
    fields) against the store's own present revision — never the
    snapshot's original revision, since that would almost always be
    stale by the time a restore actually runs. A restore is a deliberate
    overwrite, not a conflict-checked merge: the owner asked to bring
    the whole record back, not to reconcile concurrent edits.
    """
    current = store.get(tenant_id, owner_id)
    after_chat = store.update(
        tenant_id, owner_id, current.revision,
        plain_diffs=snapshot.plain_diffs, hidden_models=snapshot.hidden_models,
        default_memory_mode=snapshot.default_memory_mode,
        collapse_message_input=snapshot.collapse_message_input,
        pin_latest_prompt=snapshot.pin_latest_prompt,
    )
    return store.update_display(
        tenant_id, owner_id, after_chat.revision,
        theme=snapshot.theme, terminal_font_size=snapshot.terminal_font_size,
        terminal_shell=snapshot.terminal_shell,
        terminal_completion_enabled=snapshot.terminal_completion_enabled,
        density=snapshot.density, language=snapshot.language,
        shortcuts=snapshot.shortcuts,
    )


__all__ = ["export_preferences", "restore_preferences"]
