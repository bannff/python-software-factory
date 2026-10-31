"use client";
import { useCallback, useEffect, useState } from "react";
import { Bell } from "lucide-react";
import {
  getNotificationPreferences, listNotificationChannels,
  updateNotificationPreferences, type NotificationChannel,
  type NotificationPreferences, type NotificationPriority,
} from "./notification-settings-api";

const EVENTS = [{ kind: "scheduler_auto_paused", label: "Schedule auto-paused",
  detail: "A schedule pauses after repeated failed runs." }];
const EMPTY: NotificationPreferences = {
  globalMuted: false, mutedKinds: [], priorityOverrides: {}, revision: 1,
};

export default function NotificationSettingsPanel() {
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [preferences, setPreferences] = useState(EMPTY);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [nextChannels, nextPreferences] = await Promise.all([
        listNotificationChannels(), getNotificationPreferences(),
      ]);
      setChannels(nextChannels); setPreferences(nextPreferences);
    } catch { setError("Notification settings unavailable."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const save = async (next: NotificationPreferences) => {
    setBusy(true); setError(null);
    try { setPreferences(await updateNotificationPreferences(next)); }
    catch {
      await load();
      setError("Notification settings could not be saved. Current values were reloaded.");
    } finally { setBusy(false); }
  };
  const setMuted = (kind: string, muted: boolean) => {
    const mutedKinds = muted
      ? [...new Set([...preferences.mutedKinds, kind])]
      : preferences.mutedKinds.filter((item) => item !== kind);
    void save({ ...preferences, mutedKinds });
  };
  const setPriority = (kind: string, priority: NotificationPriority) => {
    const priorityOverrides = { ...preferences.priorityOverrides };
    if (priority === "default") delete priorityOverrides[kind];
    else priorityOverrides[kind] = priority;
    void save({ ...preferences, priorityOverrides });
  };

  return <section aria-labelledby="notification-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-4">
    <h2 id="notification-settings-title" className="text-sm font-semibold">Notifications</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">Control owner delivery by notification event.</p>
    {error && <p role="alert" className="mt-4 rounded-md border border-destructive/30 p-3 text-xs text-destructive">{error}</p>}
    {loading ? <p className="mt-4 text-xs text-muted-foreground">Loading notification settings…</p> : <>
      <div className="mt-4 rounded-md border border-border/40 p-4">
        <div className="flex items-start justify-between gap-4"><div>
          <h3 className="text-sm font-medium">Mute all event delivery</h3>
          <p className="mt-1 text-xs text-muted-foreground">Notifications still land in your inbox.</p>
        </div><label className="flex items-center gap-2 text-xs">
          <input aria-label="Mute all event delivery" type="checkbox" checked={preferences.globalMuted}
            disabled={busy} onChange={(event) => void save({ ...preferences, globalMuted: event.target.checked })} />
          {preferences.globalMuted ? "Muted" : "Active"}</label></div>
      </div>
      <div className="mt-4 grid gap-2">{EVENTS.map((event) => {
        const muted = preferences.mutedKinds.includes(event.kind);
        const priority = preferences.priorityOverrides[event.kind] || "default";
        return <article key={event.kind} className="rounded-md border border-border/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3"><div>
            <h3 className="text-sm font-medium">{event.label}</h3>
            <p className="mt-1 text-xs text-muted-foreground">{event.detail}</p>
          </div><div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-xs"><input aria-label={`Mute ${event.label}`} type="checkbox"
              checked={muted} disabled={busy} onChange={(change) => setMuted(event.kind, change.target.checked)} />Mute</label>
            <label className="grid gap-1 text-[10px] uppercase tracking-wide text-muted-foreground">Priority
              <select aria-label={`${event.label} priority`} value={priority} disabled={busy}
                onChange={(change) => setPriority(event.kind, change.target.value as NotificationPriority)}
                className="rounded-md border bg-background/50 px-2 py-1 text-xs normal-case text-foreground">
                <option value="passive">Passive</option><option value="default">Default</option><option value="critical">Critical</option>
              </select></label>
          </div></div>
        </article>;
      })}</div>
      <h3 className="mt-4 text-xs font-medium">Workspace delivery channels</h3>
      {channels.length === 0 ? <div className="mt-2 rounded-md border border-dashed p-4 text-center text-xs text-muted-foreground">
        <Bell className="mx-auto mb-2 h-5 w-5" />No delivery channels configured.</div>
        : <div className="mt-2 grid gap-2">{channels.map((channel) => <article key={channel.id}
          className="flex items-center justify-between rounded-md border border-border/40 p-3"><div>
            <p className="text-sm font-medium">{channel.name}</p><p className="text-[10px] uppercase text-violet-300">{channel.type}</p>
          </div><span className={channel.enabled ? "text-xs text-emerald-400" : "text-xs text-muted-foreground"}>
            {channel.enabled ? "Enabled" : "Disabled"}</span></article>)}</div>}
      <p className="mt-4 text-[11px] text-muted-foreground">Saved per owner with revision protection. Channel credentials are never shown or changed here.</p>
    </>}
  </section>;
}

