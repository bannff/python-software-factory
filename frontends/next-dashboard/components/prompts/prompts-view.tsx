"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Play, RefreshCw, ScrollText, Search } from "lucide-react";
import { useMcpConnection } from "@/lib/hooks/use-mcp-connection";
import {
  listFactoryPrompts, renderFactoryPrompt, type FactoryPrompt,
  type PromptCatalog, type RenderedPromptMessage,
} from "./prompts-api";

const EMPTY: PromptCatalog = { prompts: [], failedBricks: [] };

export default function PromptsView() {
  const { ready, status } = useMcpConnection();
  const [catalog, setCatalog] = useState(EMPTY);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<FactoryPrompt | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [messages, setMessages] = useState<RenderedPromptMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!ready) return;
    setLoading(true); setError(null);
    try {
      const next = await listFactoryPrompts();
      setCatalog(next);
      setSelected((current) => current
        ? next.prompts.find((item) => item.brick === current.brick && item.name === current.name) ?? null
        : null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Prompts unavailable.");
    } finally { setLoading(false); }
  }, [ready]);
  useEffect(() => { void refresh(); }, [refresh]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return needle ? catalog.prompts.filter((prompt) =>
      `${prompt.brick} ${prompt.name} ${prompt.description}`.toLowerCase().includes(needle))
      : catalog.prompts;
  }, [catalog.prompts, query]);
  const brickCount = new Set(catalog.prompts.map((prompt) => prompt.brick)).size;
  const select = (prompt: FactoryPrompt) => {
    setSelected(prompt); setValues({}); setMessages([]); setError(null);
  };
  const invoke = async () => {
    if (!selected) return;
    setRendering(true); setError(null);
    try { setMessages(await renderFactoryPrompt(selected, values)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Prompt could not be rendered."); }
    finally { setRendering(false); }
  };
  const requiredMissing = selected?.arguments.some((argument) =>
    argument.required && !(values[argument.name] ?? "").trim()) ?? false;

  return <section aria-labelledby="prompts-title">
    <div className="mb-4 flex items-start justify-between gap-3"><div>
      <h2 id="prompts-title" className="text-lg font-semibold">Prompts</h2>
      <p className="text-xs text-muted-foreground">Reusable instructions from Factory MCP prompt registries, loaded only when rendered.</p>
    </div><button type="button" aria-label="Refresh prompts" onClick={() => void refresh()}
      disabled={!ready || loading} className="rounded-md border p-2 disabled:opacity-40">
      <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></button></div>
    {error && <p role="alert" className="mb-3 rounded-md border border-destructive/30 p-3 text-xs text-destructive">{error}</p>}
    {!ready ? <p className="text-sm text-muted-foreground">MCP is {status}.</p>
      : loading && catalog.prompts.length === 0 ? <p className="text-sm text-muted-foreground">Loading MCP prompt registries…</p>
      : catalog.prompts.length === 0 ? <Empty /> : <>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <label className="relative min-w-56 flex-1"><span className="sr-only">Search prompts</span>
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input aria-label="Search prompts" value={query} onChange={(event) => setQuery(event.target.value)}
              placeholder="Search prompts and registries" className="w-full rounded-md border bg-background/50 py-2 pl-9 pr-3 text-sm" /></label>
          <span className="text-xs text-muted-foreground">{catalog.prompts.length} prompts · {brickCount} registries</span>
        </div>
        {catalog.failedBricks.length > 0 && <p className="mb-3 rounded-md border border-amber-500/30 p-3 text-xs text-amber-300">
          {catalog.failedBricks.length} registries could not be inspected: {catalog.failedBricks.join(", ")}</p>}
        <div className="grid min-h-[28rem] gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(20rem,1.1fr)]">
          <div className="grid content-start gap-2 overflow-y-auto pr-1 lg:max-h-[38rem]">
            {filtered.length === 0 ? <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">No matching prompts.</p>
              : filtered.map((prompt) => <button type="button" key={`${prompt.brick}:${prompt.name}`}
                onClick={() => select(prompt)} aria-pressed={selected?.brick === prompt.brick && selected.name === prompt.name}
                className="rounded-xl border border-border/60 bg-card/20 p-4 text-left hover:border-violet-400/50 aria-pressed:border-violet-400">
                <span className="text-[10px] font-medium uppercase tracking-wider text-violet-300">{prompt.brick}</span>
                <h3 className="mt-1 font-mono text-sm font-semibold">{prompt.name}</h3>
                <p className="mt-2 text-xs text-muted-foreground">{prompt.description || "No description provided."}</p>
                <p className="mt-2 text-[10px] text-muted-foreground">{prompt.arguments.length} arguments</p>
              </button>)}
          </div>
          <div className="rounded-xl border border-border/60 bg-card/20 p-5">
            {!selected ? <div className="grid h-full min-h-64 place-content-center text-center text-muted-foreground">
              <ScrollText className="mx-auto mb-3 h-8 w-8 text-violet-400" /><p>Select a prompt to inspect and render it.</p></div>
              : <div><p className="text-[10px] uppercase tracking-wider text-violet-300">{selected.brick} registry</p>
                <h3 className="mt-1 font-mono font-semibold">{selected.name}</h3>
                <p className="mt-2 text-xs text-muted-foreground">{selected.description || "No description provided."}</p>
                <div className="mt-4 grid gap-3">{selected.arguments.map((argument) => <label key={argument.name} className="grid gap-1 text-xs">
                  <span>{argument.name}{argument.required && <span className="text-destructive"> *</span>}</span>
                  {argument.description && <span className="text-[10px] text-muted-foreground">{argument.description}</span>}
                  <input value={values[argument.name] ?? ""} onChange={(event) => setValues((current) => ({ ...current, [argument.name]: event.target.value }))}
                    className="rounded-md border bg-background/50 px-3 py-2" /></label>)}</div>
                <button type="button" onClick={() => void invoke()} disabled={rendering || requiredMissing}
                  className="mt-4 inline-flex items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">
                  <Play className="h-3.5 w-3.5" />{rendering ? "Rendering…" : "Render through MCP"}</button>
                {messages.length > 0 && <div className="mt-4 grid gap-3">{messages.map((message, index) => <article key={index} className="rounded-md border bg-background/40 p-3">
                  <p className="mb-2 text-[10px] uppercase tracking-wider text-violet-300">{message.role}</p>
                  <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed">{message.content}</pre></article>)}</div>}
              </div>}
          </div>
        </div>
      </>}
  </section>;
}

function Empty() { return <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
  <ScrollText className="mx-auto mb-3 h-8 w-8 text-violet-400" /><p>No MCP prompts are registered.</p></div>; }
