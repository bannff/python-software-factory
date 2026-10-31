"use client";
import { Code2, ShieldAlert, SquareCode } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  getApprovalPolicy, listApprovalToolNames, updateApprovalPolicy,
  type ApprovalPolicy,
} from "./approval-policy-api";

const POSTURE = [
  { icon: Code2, title: "Local commands", detail: "Project checks use a short list of approved test and build commands. Unsafe paths, URLs, and arguments are refused." },
  { icon: ShieldAlert, title: "Confirmations", detail: "Only tools you add below ask you to Approve or Deny. An empty list keeps unattended autonomy." },
  { icon: SquareCode, title: "Embedded content", detail: "Embedded pages run in a restricted frame. Tool actions and outside origins must pass allowlists." },
] as const;
const EMPTY: ApprovalPolicy = { toolNames: [], revision: 0 };

export default function SecuritySettingsPanel() {
  const [policy, setPolicy] = useState(EMPTY);
  const [catalog, setCatalog] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = async () => {
    setLoading(true); setError(null);
    try {
      const [saved, names] = await Promise.all([getApprovalPolicy(), listApprovalToolNames()]);
      setPolicy(saved); setCatalog(names);
    } catch { setError("Approval settings are unavailable."); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return policy.toolNames;
    return catalog.filter((name) => name.toLowerCase().includes(needle)).slice(0, 50);
  }, [catalog, policy.toolNames, query]);
  const toggle = async (name: string, required: boolean) => {
    const toolNames = required
      ? [...new Set([...policy.toolNames, name])].sort()
      : policy.toolNames.filter((item) => item !== name);
    setBusy(true); setError(null);
    try { setPolicy(await updateApprovalPolicy({ ...policy, toolNames })); }
    catch { await load(); setError("Approval settings could not be saved. Current values were reloaded."); }
    finally { setBusy(false); }
  };
  return <section aria-labelledby="security-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="security-settings-title" className="text-sm font-semibold">Security</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">Choose the tools that must ask before running.</p>
    <div className="mt-4 grid gap-3 sm:grid-cols-3">{POSTURE.map((item) => <article key={item.title} className="rounded-md border border-border/40 p-3">
      <item.icon className="h-4 w-4 text-violet-400" /><h3 className="mt-2 text-sm font-medium">{item.title}</h3>
      <p className="mt-1 text-xs text-muted-foreground">{item.detail}</p>
    </article>)}</div>
    <div className="mt-4 rounded-md border border-border/40 p-4">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><h3 className="text-sm font-medium">Require approval</h3>
        <p className="mt-1 text-xs text-muted-foreground">Search exact tool names. Selected tools pause in the existing chat approval card.</p></div>
        <span className="text-xs text-muted-foreground">{policy.toolNames.length} selected</span></div>
      <label className="mt-3 block"><span className="sr-only">Search approval tools</span><input aria-label="Search approval tools" value={query}
        onChange={(event) => setQuery(event.target.value)} placeholder="Search tools to add…" disabled={loading || busy}
        className="w-full rounded-md border border-border/60 bg-background/50 px-3 py-2 text-xs outline-none" /></label>
      {error && <p role="alert" className="mt-3 text-xs text-destructive">{error}</p>}
      {loading ? <p className="mt-3 text-xs text-muted-foreground">Loading approval settings…</p>
        : rows.length === 0 ? <p className="mt-3 text-xs text-muted-foreground">{query ? "No matching tools." : "No tools require approval. Agents run unattended."}</p>
          : <div className="mt-3 max-h-48 space-y-1 overflow-y-auto">{rows.map((name) => <label key={name} className="flex items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-muted/30">
            <input type="checkbox" checked={policy.toolNames.includes(name)} disabled={busy}
              onChange={(event) => void toggle(name, event.target.checked)} /><code className="break-all">{name}</code></label>)}</div>}
    </div>
  </section>;
}
