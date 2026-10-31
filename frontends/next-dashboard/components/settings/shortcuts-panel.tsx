"use client";

import { useState } from "react";
import { updateDisplayPreferences } from "./display-preferences-api";
import { announceDisplayPreferences, useDisplayPreferences } from "./use-display-preferences";
import { SHORTCUT_ACTIONS, chordFromEvent, effectiveChord, formatChord } from "@/lib/shortcuts";

/**
 * Keyboard reference + owner overrides. Remappable actions persist through
 * the durable Display preference (full-object revision CAS); structural keys
 * (arrows/Home/End) are listed but fixed.
 */
export default function ShortcutsPanel() {
  const { preferences, loading, error, refresh } = useDisplayPreferences();
  const [recording, setRecording] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const save = async (shortcuts: Record<string, string>) => {
    setBusy(true); setNotice(null);
    try { announceDisplayPreferences(await updateDisplayPreferences({ ...preferences, shortcuts })); }
    catch (cause) {
      const conflict = cause instanceof Error && cause.message.includes("conflict");
      setNotice(conflict ? "Shortcuts changed elsewhere. Current values were reloaded." : "That shortcut couldn’t be saved.");
      if (conflict) refresh();
    }
    finally { setBusy(false); setRecording(null); }
  };

  const record = (actionId: string) => (event: React.KeyboardEvent<HTMLButtonElement>) => {
    event.preventDefault();
    if (event.key === "Escape") { setRecording(null); return; }
    const chord = chordFromEvent(event);
    if (!chord) return;
    const taken = SHORTCUT_ACTIONS.find((item) => item.id !== actionId && effectiveChord(item.id, preferences.shortcuts) === chord);
    if (taken) { setNotice(`${formatChord(chord).join(" ")} is already used by “${taken.label}”.`); return; }
    const next = { ...preferences.shortcuts };
    const action = SHORTCUT_ACTIONS.find((item) => item.id === actionId);
    if (action?.defaultChord === chord) delete next[actionId]; else next[actionId] = chord;
    void save(next);
  };

  const reset = (actionId: string) => {
    const next = { ...preferences.shortcuts }; delete next[actionId]; void save(next);
  };

  return <section aria-labelledby="shortcuts-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-4">
    <h2 id="shortcuts-settings-title" className="text-sm font-semibold">Shortcuts</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">Click a shortcut to record a new key combination. Saved per owner; Escape cancels.</p>
    {(error || notice) && <p role="alert" className="mt-3 text-xs text-destructive">{notice || error}</p>}
    {loading ? <p className="mt-3 text-xs text-muted-foreground">Loading shortcuts…</p> : <div className="mt-3 overflow-hidden rounded-md border border-border/40">
      {SHORTCUT_ACTIONS.map((action, index) => {
        const chord = effectiveChord(action.id, preferences.shortcuts);
        const overridden = action.id in preferences.shortcuts;
        return <article key={action.id} className={`flex flex-wrap items-center justify-between gap-3 p-2 ${index ? "border-t border-border/40" : ""}`}>
          <div><p className="text-[10px] font-medium uppercase tracking-wider text-violet-300">{action.area}</p>
            <p className="mt-0.5 text-sm">{action.label}</p></div>
          <div className="flex items-center gap-1.5">
            {chord === null ? action.fixedKeys?.map((key) => <kbd key={key} className="min-w-8 rounded border border-border bg-muted/30 px-2 py-1 text-center font-mono text-[11px] shadow-sm">{key}</kbd>)
              : <>
                <button type="button" aria-label={`Change shortcut for ${action.label}`} disabled={busy}
                  aria-pressed={recording === action.id}
                  onClick={() => setRecording(recording === action.id ? null : action.id)}
                  onKeyDown={recording === action.id ? record(action.id) : undefined}
                  className={`flex gap-1 rounded border px-1 py-0.5 ${recording === action.id ? "border-violet-400 ring-1 ring-violet-400/50" : "border-transparent hover:border-border"}`}>
                  {recording === action.id ? <span className="px-1 font-mono text-[11px] text-violet-300">Press keys…</span>
                    : formatChord(chord).map((key) => <kbd key={key} className="min-w-8 rounded border border-border bg-muted/30 px-2 py-1 text-center font-mono text-[11px] shadow-sm">{key}</kbd>)}
                </button>
                {overridden && <button type="button" onClick={() => reset(action.id)} disabled={busy}
                  aria-label={`Reset shortcut for ${action.label}`} className="text-[10px] text-muted-foreground hover:text-foreground">Reset</button>}
              </>}
          </div>
        </article>;
      })}
    </div>}
  </section>;
}
