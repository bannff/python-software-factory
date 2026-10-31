"use client";

import { useState } from "react";
import { Folder, FolderPlus, Loader2, Pencil, Trash2 } from "lucide-react";
import type { ArtifactFolder } from "./artifact-types";

interface FolderSidebarProps {
  folders: ArtifactFolder[];
  activeFolderId: string | null;
  onSelect: (folderId: string | null) => void;
  onCreate: (name: string, parentId: string | null) => Promise<void>;
  onRename: (folder: ArtifactFolder, name: string) => Promise<void>;
  onDelete: (folder: ArtifactFolder) => Promise<void>;
}

/**
 * Folder tree for the Artifact library (feature-map row 63's remaining
 * gap). A flat depth-ordered list rendered with indentation reads as a
 * tree without needing real recursive expand/collapse state — every
 * folder's own ``path``/``depth`` (from the real backend model) already
 * encodes its position.
 */
export function FolderSidebar({ folders, activeFolderId, onSelect, onCreate, onRename, onDelete }: FolderSidebarProps) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [busy, setBusy] = useState(false);
  const sorted = [...folders].sort((a, b) => a.path.localeCompare(b.path));

  const submitCreate = async () => {
    if (!newName.trim()) return;
    setBusy(true);
    await onCreate(newName.trim(), activeFolderId);
    setBusy(false);
    setNewName(""); setCreating(false);
  };

  const submitRename = async (folder: ArtifactFolder) => {
    if (!renameValue.trim()) return;
    setBusy(true);
    await onRename(folder, renameValue.trim());
    setBusy(false);
    setRenaming(null);
  };

  return (
    <nav aria-label="Artifact folders" className="flex flex-col gap-1 rounded-xl border border-border/60 bg-card/20 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Folders</span>
        <button type="button" onClick={() => setCreating((v) => !v)} aria-label="New folder"
          className="rounded-md p-1 text-muted-foreground hover:bg-accent/40 hover:text-foreground">
          <FolderPlus className="h-3.5 w-3.5" />
        </button>
      </div>
      <button type="button" onClick={() => onSelect(null)} aria-current={activeFolderId === null}
        className={`flex items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-sm ${activeFolderId === null ? "bg-violet-500/15" : "hover:bg-accent/30"}`}>
        <Folder className="h-3.5 w-3.5" /> All artifacts
      </button>
      {creating && (
        <div className="flex items-center gap-1 px-2 py-1">
          <input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="Folder name" autoFocus
            onKeyDown={(event) => { if (event.key === "Enter") void submitCreate(); }}
            className="w-full rounded-md border border-border/60 bg-background/50 px-2 py-1 text-xs text-foreground" />
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : (
            <button type="button" onClick={() => void submitCreate()} className="rounded-md bg-violet-500 px-2 py-1 text-[10px] text-white">Add</button>
          )}
        </div>
      )}
      {sorted.map((folder) => (
        <div key={folder.id} className="group flex items-center gap-1" style={{ paddingLeft: `${(folder.depth - 1) * 12}px` }}>
          {renaming === folder.id ? (
            <input value={renameValue} onChange={(event) => setRenameValue(event.target.value)} autoFocus
              onKeyDown={(event) => { if (event.key === "Enter") void submitRename(folder); if (event.key === "Escape") setRenaming(null); }}
              onBlur={() => void submitRename(folder)}
              className="w-full rounded-md border border-border/60 bg-background/50 px-2 py-1 text-xs text-foreground" />
          ) : (
            <button type="button" onClick={() => onSelect(folder.id)} aria-current={activeFolderId === folder.id}
              className={`flex flex-1 items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-sm ${activeFolderId === folder.id ? "bg-violet-500/15" : "hover:bg-accent/30"}`}>
              <Folder className="h-3.5 w-3.5 shrink-0" />
              <span className="min-w-0 truncate">{folder.name}</span>
              <span className="text-[10px] text-muted-foreground">{folder.item_count}</span>
            </button>
          )}
          <div className="hidden gap-0.5 group-hover:flex">
            <button type="button" aria-label={`Rename folder ${folder.name}`} onClick={() => { setRenaming(folder.id); setRenameValue(folder.name); }}
              className="rounded-md p-1 text-muted-foreground hover:text-foreground"><Pencil className="h-3 w-3" /></button>
            <button type="button" aria-label={`Delete folder ${folder.name}`} onClick={() => void onDelete(folder)}
              className="rounded-md p-1 text-muted-foreground hover:text-destructive"><Trash2 className="h-3 w-3" /></button>
          </div>
        </div>
      ))}
    </nav>
  );
}
