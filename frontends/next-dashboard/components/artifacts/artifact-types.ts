export type ArtifactKind = "widget" | "html" | "markdown" | "svg" | "json" | "text";

export type Artifact = {
  slug: string;
  name: string;
  description: string;
  tags: string[];
  kind: ArtifactKind;
  content: string;
  version: number;
  revision: number;
  updated_at: string;
  folder_id: string | null;
};

export type ArtifactFolder = {
  id: string;
  parent_id: string | null;
  name: string;
  revision: number;
  path: string;
  depth: number;
  item_count: number;
};

export type ArtifactVersion = {
  version: number;
  kind: ArtifactKind;
  actor_kind: "agent" | "human";
  event_type: "created" | "updated" | "reverted";
  created_at: string;
};

export type ArtifactComment = {
  id: string;
  root_id: string;
  parent_id: string | null;
  body: string;
  actor_kind: "agent" | "human";
  status: "open" | "review" | "resolved";
  revision: number;
  created_at: string;
  anchor_text: string | null;
};

export function rows<T>(raw: unknown, key: string): T[] {
  if (!raw || typeof raw !== "object") return [];
  const value = (raw as Record<string, unknown>)[key];
  return Array.isArray(value) ? value as T[] : [];
}
