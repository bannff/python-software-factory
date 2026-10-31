"use client";
import { KeyRound, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import {
  deleteOwnerSecret, listOwnerSecretNames, setOwnerSecret,
} from "./secrets-settings-api";

export default function SecretsSettingsPanel() {
  const [names, setNames] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const load = async () => {
    setLoading(true); setError(null);
    try { setNames(await listOwnerSecretNames()); }
    catch { setError("Secrets are unavailable."); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const add = async () => {
    const trimmedName = name.trim();
    if (!trimmedName || !value) return;
    setBusy(true); setError(null); setSaved(null);
    try {
      await setOwnerSecret(trimmedName, value);
      setName(""); setValue(""); setSaved(trimmedName);
      await load();
    } catch { setError("Secret could not be saved."); }
    finally { setBusy(false); }
  };

  const remove = async (target: string) => {
    setBusy(true); setError(null); setSaved(null);
    try { await deleteOwnerSecret(target); await load(); }
    catch { setError("Secret could not be deleted."); }
    finally { setBusy(false); }
  };

  return <section aria-labelledby="secrets-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="secrets-settings-title" className="text-sm font-semibold">Secrets</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">
      Store your own API keys and tokens by name. Values are encrypted and never shown again after saving.
    </p>

    <div className="mt-4 rounded-md border border-border/40 p-4">
      <h3 className="text-sm font-medium">Add a secret</h3>
      <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
        <label className="block"><span className="sr-only">Secret name</span>
          <input aria-label="Secret name" value={name} disabled={busy}
            onChange={(event) => setName(event.target.value)} placeholder="e.g. JIRA_API_TOKEN"
            className="w-full rounded-md border border-border/60 bg-background/50 px-3 py-2 text-xs outline-none" /></label>
        <label className="block"><span className="sr-only">Secret value</span>
          <input aria-label="Secret value" type="password" value={value} disabled={busy}
            onChange={(event) => setValue(event.target.value)} placeholder="Value"
            className="w-full rounded-md border border-border/60 bg-background/50 px-3 py-2 text-xs outline-none" /></label>
        <button type="button" onClick={() => void add()} disabled={busy || !name.trim() || !value}
          className="rounded-md bg-violet-600 px-3 py-2 text-xs font-medium text-white disabled:opacity-50">
          Save
        </button>
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">
        The value is never shown again after saving — only the name is listed below.
      </p>
      {saved && <p role="status" className="mt-2 text-xs text-emerald-400">Saved &ldquo;{saved}&rdquo;.</p>}
    </div>

    {error && <p role="alert" className="mt-4 rounded-md border border-destructive/30 p-3 text-xs text-destructive">{error}</p>}

    <h3 className="mt-4 text-xs font-medium">Stored secrets</h3>
    {loading ? <p className="mt-2 text-xs text-muted-foreground">Loading secrets…</p>
      : names.length === 0 ? <div className="mt-2 rounded-md border border-dashed p-4 text-center text-xs text-muted-foreground">
          <KeyRound className="mx-auto mb-2 h-5 w-5" />No secrets stored yet.</div>
        : <div className="mt-2 grid gap-2">{names.map((storedName) => (
            <article key={storedName} className="flex items-center justify-between rounded-md border border-border/40 p-3">
              <code className="text-sm">{storedName}</code>
              <button type="button" aria-label={`Delete ${storedName}`} onClick={() => void remove(storedName)}
                disabled={busy} className="rounded p-1 text-muted-foreground hover:text-destructive disabled:opacity-50">
                <Trash2 className="h-4 w-4" />
              </button>
            </article>
          ))}</div>}
  </section>;
}
