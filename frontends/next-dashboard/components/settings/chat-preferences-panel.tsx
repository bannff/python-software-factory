"use client";
import { useState } from "react";
import { useModelCatalog } from "@/lib/hooks/use-model-catalog";
import { updateChatPreferences, type ChatPreferences, type DefaultMemoryMode } from "./chat-preferences-api";
import { announceChatPreferences, useChatPreferences } from "./use-chat-preferences";

const MEMORY_MODES: { id: DefaultMemoryMode; label: string; hint: string }[] = [
  { id: "persistent", label: "Persistent", hint: "Saved to history; memory and lessons can learn from it." },
  { id: "incognito", label: "Incognito", hint: "Kept in history for this session only; never feeds memory or lessons." },
  { id: "temporary", label: "Temporary", hint: "Not saved to history; never feeds memory or lessons." },
];

export default function ChatPreferencesPanel() {
  const { preferences, loading, error, refresh } = useChatPreferences();
  // Governance list: every model the deployment can offer must be toggleable.
  const catalog = useModelCatalog({ scope: "all" });
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const save = async (next: ChatPreferences) => {
    setBusy(true); setSaveError(null);
    try { announceChatPreferences(await updateChatPreferences(next)); }
    catch { setSaveError("Preferences changed elsewhere. Reloaded the current values."); refresh(); }
    finally { setBusy(false); }
  };
  const setPlain = (plainDiffs: boolean) => void save({ ...preferences, plainDiffs });
  const setDefaultMemoryMode = (defaultMemoryMode: DefaultMemoryMode) => void save({ ...preferences, defaultMemoryMode });
  const setCollapseMessageInput = (collapseMessageInput: boolean) => void save({ ...preferences, collapseMessageInput });
  const setPinLatestPrompt = (pinLatestPrompt: boolean) => void save({ ...preferences, pinLatestPrompt });
  const setVisible = (model: string, visible: boolean) => {
    const hiddenModels = visible
      ? preferences.hiddenModels.filter((item) => item !== model)
      : [...preferences.hiddenModels.filter((item) => item !== model), model];
    void save({ ...preferences, hiddenModels });
  };

  return <section aria-labelledby="chat-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="chat-settings-title" className="text-sm font-semibold">Chat</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">Choose how development output and model choices appear.</p>
    {(error || saveError) && <p role="alert" className="mt-4 rounded-md border border-destructive/30 p-3 text-xs text-destructive">{saveError || error}</p>}
    {loading ? <p className="mt-4 text-xs text-muted-foreground">Loading chat preferences…</p> : <>
      <div className="mt-4 rounded-md border border-border/40 p-4">
        <h3 className="text-sm font-medium">Default memory mode</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Applies to new chats you start from the dashboard. An explicit per-chat choice always wins;
          app-owned and direct API sessions keep their own mode.
        </p>
        <div role="radiogroup" aria-label="Default memory mode" className="mt-3 grid gap-2">
          {MEMORY_MODES.map((option) => <label key={option.id} className="flex items-start gap-2 text-xs">
            <input
              type="radio" name="default-memory-mode" aria-label={option.label}
              checked={preferences.defaultMemoryMode === option.id} disabled={busy}
              onChange={() => setDefaultMemoryMode(option.id)}
            />
            <span><span className="font-medium text-foreground">{option.label}</span>
              <span className="block text-muted-foreground">{option.hint}</span></span>
          </label>)}
        </div>
      </div>
      <div className="mt-4 rounded-md border border-border/40 p-4">
        <div className="flex items-start justify-between gap-4"><div><h3 className="text-sm font-medium">Plain diffs</h3>
          <p className="mt-1 text-xs text-muted-foreground">Show git changes as plain text instead of highlighting added and removed lines.</p></div>
          <label className="flex items-center gap-2 text-xs"><input aria-label="Plain diffs" type="checkbox" checked={preferences.plainDiffs}
            disabled={busy} onChange={(event) => setPlain(event.target.checked)} />{preferences.plainDiffs ? "On" : "Off"}</label></div>
      </div>
      <div className="mt-4 rounded-md border border-border/40 p-4">
        <div className="flex items-start justify-between gap-4"><div><h3 className="text-sm font-medium">Collapse the message input</h3>
          <p className="mt-1 text-xs text-muted-foreground">Puts the composer away while you read a long reply, leaving a bar to restore it. Off by default.</p></div>
          <label className="flex items-center gap-2 text-xs"><input aria-label="Collapse the message input" type="checkbox" checked={preferences.collapseMessageInput}
            disabled={busy} onChange={(event) => setCollapseMessageInput(event.target.checked)} />{preferences.collapseMessageInput ? "On" : "Off"}</label></div>
      </div>
      <div className="mt-4 rounded-md border border-border/40 p-4">
        <div className="flex items-start justify-between gap-4"><div><h3 className="text-sm font-medium">Pin the latest turn</h3>
          <p className="mt-1 text-xs text-muted-foreground">Keeps your most recent prompt visible at the top of the chat while a long reply scrolls. Off by default.</p></div>
          <label className="flex items-center gap-2 text-xs"><input aria-label="Pin the latest turn" type="checkbox" checked={preferences.pinLatestPrompt}
            disabled={busy} onChange={(event) => setPinLatestPrompt(event.target.checked)} />{preferences.pinLatestPrompt ? "On" : "Off"}</label></div>
      </div>
      <div className="mt-4 rounded-md border border-border/40 p-4"><h3 className="text-sm font-medium">Model picker visibility</h3>
        <p className="mt-1 text-xs text-muted-foreground">Hidden models stay configured but do not appear in the chat picker.</p>
        {catalog.loading && <p className="mt-3 text-xs text-muted-foreground">Loading models…</p>}
        {catalog.error && <p className="mt-3 text-xs text-destructive">{catalog.error}</p>}
        {!catalog.loading && !catalog.error && <div className="mt-3 grid gap-3 sm:grid-cols-2">{catalog.groups.map((group) => <fieldset key={group.provider} className="rounded-md bg-muted/20 p-3">
          <legend className="px-1 text-[10px] font-medium uppercase tracking-wider text-violet-300">{group.provider}</legend>
          <div className="grid gap-2">{group.models.map((model) => <label key={model.model_id} className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={!preferences.hiddenModels.includes(model.model_id)} disabled={busy}
              onChange={(event) => setVisible(model.model_id, event.target.checked)} />
            <span className="truncate" title={model.model_id}>{model.model}</span></label>)}</div>
        </fieldset>)}</div>}
      </div>
      <p className="mt-4 text-[11px] text-muted-foreground">Saved per owner with revision protection and applied to every open Companion X chat.</p>
    </>}
  </section>;
}
