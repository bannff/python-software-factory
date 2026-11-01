"use client";

import { useEffect, useMemo, useState } from "react";
import { useToolData } from "@companion-x/shared-renderer";
import { Box, FileText, Loader2, Plus, RefreshCw, Search } from "lucide-react";
import { ArtifactDetail } from "./artifact-detail";
import { ArtifactCreateDialog } from "./artifact-create-dialog";
import { FolderSidebar } from "./folder-sidebar";
import { createFolder, deleteFolder, listFolders, renameFolder } from "./artifact-actions";
import type { Artifact, ArtifactFolder } from "./artifact-types";

function artifactsFrom(raw: unknown): Artifact[] {
  if (!raw || typeof raw !== "object") return [];
  const rows = (raw as { artifacts?: unknown }).artifacts;
  if (!Array.isArray(rows)) return [];
  return rows.filter((row): row is Artifact => Boolean(
    row && typeof row === "object" && typeof row.slug === "string"
      && typeof row.name === "string" && typeof row.content === "string",
  ));
}

export default function ArtifactsView() {
  const { data, loading, error, refetch } = useToolData(
    "artifacts_list", { limit: 100, offset: 0 },
  );
  const artifacts = useMemo(() => artifactsFrom(data), [data]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [folders, setFolders] = useState<ArtifactFolder[]>([]);
  const [activeFolderId, setActiveFolderId] = useState<string | null>(null);
  // A just-deleted artifact leaves `artifacts_list` (tombstones are filtered
  // out server-side), so its detail panel keeps rendering from this retained
  // record — that is the only place the permanent purge action is reachable.
  const [tombstoned, setTombstoned] = useState<Artifact | null>(null);
  const refreshFolders = () => { void listFolders().then(setFolders).catch(() => setFolders([])); };
  useEffect(() => { refreshFolders(); }, []);
  useEffect(() => {
    const parts = window.location.pathname.split("/").filter(Boolean);
    if (parts[0] === "artifacts" && parts[1]) setSelected(decodeURIComponent(parts[1]));
  }, []);
  const inFolder = artifacts.filter((item) => item.folder_id === activeFolderId);
  const visible = inFolder.filter((item) =>
    `${item.name} ${item.slug} ${item.tags.join(" ")}`.toLowerCase().includes(query.toLowerCase()),
  );
  const listed = artifacts.find((item) => item.slug === selected) ?? null;
  const active = listed ?? (tombstoned?.slug === selected ? tombstoned : null);
  const activeTombstoned = listed === null && tombstoned !== null && tombstoned.slug === selected;
  const open = (slug: string) => {
    window.history.pushState({}, "", `/artifacts/${encodeURIComponent(slug)}`);
    setTombstoned(null);
    setSelected(slug);
  };
  const created = (artifact: Artifact) => {
    setCreating(false); refetch(); open(artifact.slug);
  };
  const onCreateFolder = async (name: string, parentId: string | null) => {
    await createFolder(name, parentId); refreshFolders();
  };
  const onRenameFolder = async (folder: ArtifactFolder, name: string) => {
    await renameFolder(folder, name); refreshFolders();
  };
  const onDeleteFolder = async (folder: ArtifactFolder) => {
    await deleteFolder(folder);
    if (activeFolderId === folder.id) setActiveFolderId(folder.parent_id);
    refreshFolders();
  };

  return (
    <section className="mx-auto flex min-h-full w-full max-w-7xl flex-col gap-5 p-6" aria-labelledby="artifacts-title">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-400">Library</p>
          <h1 id="artifacts-title" className="mt-1 text-2xl font-semibold tracking-tight">Artifacts</h1>
          <p className="mt-1 text-sm text-muted-foreground">Versioned work, ready to reopen and refine.</p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setCreating(true)} className="inline-flex items-center gap-1.5 rounded-lg bg-violet-500 px-3 py-2 text-xs text-white hover:bg-violet-500/90">
            <Plus className="h-3.5 w-3.5" /> New artifact
          </button>
          <button type="button" onClick={refetch} aria-label="Refresh artifacts" className="rounded-lg border border-border/60 p-2 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>
      <div className="grid gap-4 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <FolderSidebar folders={folders} activeFolderId={activeFolderId} onSelect={setActiveFolderId}
          onCreate={onCreateFolder} onRename={onRenameFolder} onDelete={onDeleteFolder} />
        <div className="flex flex-col gap-4">
          <label className="flex max-w-md items-center gap-2 rounded-lg border border-border/60 bg-card/30 px-3 py-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <span className="sr-only">Filter artifacts</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter by name, slug, or tag" className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground" />
          </label>
          {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm"><span>Artifacts unavailable: {error}</span><button type="button" onClick={refetch} className="rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50">Retry</button></div>}
          {creating && <ArtifactCreateDialog onCreated={created} onClose={() => setCreating(false)} />}
          {loading && artifacts.length === 0 && <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading artifacts…</div>}
          {!loading && !error && visible.length === 0 && !creating && <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-border/60 p-10 text-center"><Box className="h-8 w-8 text-violet-400/70" /><h2 className="mt-3 font-medium">{activeFolderId ? "Empty folder" : "No artifacts yet"}</h2><p className="mt-1 max-w-sm text-sm text-muted-foreground">{activeFolderId ? "Move an artifact here, or ask Companion X to save one directly into it." : "Ask Companion X to save a report, widget, or document, or click New artifact above."}</p></div>}
          {active && <ArtifactDetail artifact={active} tombstoned={activeTombstoned} onChanged={refetch} onDeleted={setTombstoned} onClose={() => { window.history.pushState({}, "", "/artifacts"); setTombstoned(null); setSelected(null); }} />}
          {visible.length > 0 && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{visible.map((item) => <button key={item.slug} type="button" onClick={() => open(item.slug)} className="group rounded-xl border border-border/60 bg-card/30 p-4 text-left transition-all hover:-translate-y-0.5 hover:border-violet-500/40 hover:bg-card/60 hover:shadow-lg hover:shadow-violet-500/5"><div className="flex items-start gap-3"><span className="rounded-lg bg-violet-500/10 p-2 text-violet-400"><FileText className="h-4 w-4" /></span><div className="min-w-0"><h2 className="truncate font-medium">{item.name}</h2><p className="truncate text-xs text-muted-foreground">{item.slug} · v{item.version}</p></div></div><p className="mt-3 line-clamp-2 min-h-10 text-sm text-muted-foreground">{item.description || `A ${item.kind} artifact`}</p><div className="mt-3 flex flex-wrap gap-1">{item.tags.slice(0, 4).map((tag) => <span key={tag} className="rounded-full bg-muted/60 px-2 py-0.5 text-[10px] text-muted-foreground">{tag}</span>)}</div></button>)}</div>}
        </div>
      </div>
    </section>
  );
}
