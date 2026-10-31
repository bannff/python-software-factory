"use client";
import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import {
  DISPLAY_LANGUAGES, updateDisplayPreferences,
  type DisplayDensity, type DisplayPreferences, type DisplayTheme,
} from "./display-preferences-api";
import { announceDisplayPreferences, useDisplayPreferences } from "./use-display-preferences";
import { listTerminalShells } from "@/lib/terminal-api";

export default function DisplayPreferencesPanel() {
  const { setTheme } = useTheme();
  const { preferences, loading, error, refresh } = useDisplayPreferences();
  const [busy, setBusy] = useState(false); const [saveError, setSaveError] = useState<string | null>(null);
  const [shells, setShells] = useState<string[]>([]);
  useEffect(() => { void listTerminalShells().then((r) => setShells(r.shells)).catch(() => {}); }, []);
  const save = async (next: DisplayPreferences) => {
    setBusy(true); setSaveError(null);
    try { const saved = await updateDisplayPreferences(next); announceDisplayPreferences(saved); setTheme(saved.theme); }
    catch { setSaveError("Display settings changed elsewhere. Current values were reloaded."); refresh(); }
    finally { setBusy(false); }
  };
  return <section aria-labelledby="display-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="display-settings-title" className="text-sm font-semibold">Display</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">Choose the dashboard theme and Terminal settings.</p>
    {(error || saveError) && <p role="alert" className="mt-4 text-xs text-destructive">{saveError || error}</p>}
    {loading ? <p className="mt-4 text-xs text-muted-foreground">Loading display preferences…</p> : <div className="mt-4 grid gap-4">
      <label className="grid gap-1 text-xs"><span className="font-medium">Theme</span><span className="text-muted-foreground">System follows your device appearance.</span>
        <select aria-label="Theme" value={preferences.theme} disabled={busy} onChange={(event) => void save({ ...preferences, theme: event.target.value as DisplayTheme })}
          className="mt-1 rounded-md border bg-background/50 px-3 py-2"><option value="system">System</option><option value="dark">Dark</option><option value="light">Light</option></select></label>
      <label className="grid gap-1 text-xs"><span className="font-medium">Density</span><span className="text-muted-foreground">Compact tightens spacing across the whole dashboard.</span>
        <select aria-label="Density" value={preferences.density} disabled={busy} onChange={(event) => void save({ ...preferences, density: event.target.value as DisplayDensity })}
          className="mt-1 rounded-md border bg-background/50 px-3 py-2"><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label>
      <label className="grid gap-1 text-xs"><span className="font-medium">Language</span><span className="text-muted-foreground">Sets the page language for dates, numbers, and assistive technology. Interface text is English for now.</span>
        <select aria-label="Language" value={preferences.language} disabled={busy} onChange={(event) => void save({ ...preferences, language: event.target.value })}
          className="mt-1 rounded-md border bg-background/50 px-3 py-2">
          {DISPLAY_LANGUAGES.some((item) => item.tag === preferences.language) ? null : <option value={preferences.language}>{preferences.language}</option>}
          {DISPLAY_LANGUAGES.map((item) => <option key={item.tag} value={item.tag}>{item.label}</option>)}
        </select></label>
      <label className="grid gap-1 text-xs"><span className="font-medium">Terminal font size</span><span className="text-muted-foreground">Applies immediately to the docked Terminal panel.</span>
        <input aria-label="Terminal font size" type="range" min="10" max="18" value={preferences.terminalFontSize} disabled={busy}
          onChange={(event) => void save({ ...preferences, terminalFontSize: Number(event.target.value) })} />
        <output>{preferences.terminalFontSize} px</output></label>
      <label className="grid gap-1 text-xs"><span className="font-medium">Default shell</span><span className="text-muted-foreground">Used for new Terminal sessions. Leave as System default to follow your account shell.</span>
        <select aria-label="Default shell" value={preferences.terminalShell ?? ""} disabled={busy}
          onChange={(event) => void save({ ...preferences, terminalShell: event.target.value || null })}
          className="mt-1 rounded-md border bg-background/50 px-3 py-2">
          <option value="">System default</option>
          {shells.map((shell) => <option key={shell} value={shell}>{shell}</option>)}
        </select></label>
      <label className="flex items-center gap-2 text-xs"><input type="checkbox" aria-label="Enable Terminal completion"
          checked={preferences.terminalCompletionEnabled} disabled={busy}
          onChange={(event) => void save({ ...preferences, terminalCompletionEnabled: event.target.checked })} />
        <span><span className="font-medium">Enable Terminal completion</span><br />
          <span className="text-muted-foreground">Show command, option, and file-path suggestions while typing. Shell Tab completion still works when off.</span></span></label>
      <p className="text-[11px] text-muted-foreground">Saved per owner with revision protection.</p>
    </div>}
  </section>;
}
