import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export const EXPORT_KINDS = ["memory", "kb", "lessons", "schedules", "preferences"] as const;
export type ExportKind = (typeof EXPORT_KINDS)[number];

export interface ExportKindSummary {
  kind: string;
  count: number;
  excluded: number;
  digest: string;
}

export interface ExportPreview {
  bundleVersion: number;
  adapter: string;
  contentDigest: string;
  kinds: ExportKindSummary[];
}

export interface ExportResult extends ExportPreview {
  path: string;
  bytesWritten: number;
}

function record(raw: unknown): Record<string, unknown> {
  if (!raw || typeof raw !== "object") throw new Error("Export returned invalid data.");
  return raw as Record<string, unknown>;
}

function summaries(raw: unknown): ExportKindSummary[] {
  return Array.isArray(raw) ? raw.flatMap((item) => {
    const value = record(item);
    return typeof value.kind === "string" && typeof value.digest === "string"
      ? [{ kind: value.kind, count: Number(value.count) || 0,
        excluded: Number(value.excluded) || 0, digest: value.digest }] : [];
  }) : [];
}

export async function previewExport(kinds?: ExportKind[]): Promise<ExportPreview> {
  const data = record(unwrapToolData(await callTool("portability_export_preview", { kinds })));
  if (typeof data.content_digest !== "string") throw new Error("Export preview is unavailable.");
  return {
    bundleVersion: Number(data.bundle_version) || 1,
    adapter: typeof data.adapter === "string" ? data.adapter : "companion-x-v1",
    contentDigest: data.content_digest, kinds: summaries(data.kinds),
  };
}

export async function runExport(destinationName: string, kinds?: ExportKind[]): Promise<ExportResult> {
  const data = record(unwrapToolData(await callTool("portability_export", {
    destination_name: destinationName, kinds,
  })));
  if (typeof data.path !== "string" || typeof data.content_digest !== "string") {
    throw new Error("Export could not be written.");
  }
  return {
    path: data.path, bytesWritten: Number(data.bytes_written) || 0,
    bundleVersion: Number(data.bundle_version) || 1,
    adapter: typeof data.adapter === "string" ? data.adapter : "companion-x-v1",
    contentDigest: data.content_digest, kinds: summaries(data.kinds),
  };
}

export interface BundlePreview {
  planDigest: string;
  status: string;
  reports: { kind: string; found: number; eligible: number; excluded: number }[];
  unsupportedKinds: string[];
}

export async function previewBundleImport(bundleRef: string, kinds?: string[]): Promise<BundlePreview> {
  const data = record(unwrapToolData(await callTool("migration_preview_bundle", {
    bundle_ref: bundleRef, kinds,
  })));
  if (typeof data.plan_digest !== "string" || !Array.isArray(data.reports)) {
    throw new Error("Bundle preview is unavailable.");
  }
  return {
    planDigest: data.plan_digest,
    status: typeof data.status === "string" ? data.status : "planned",
    reports: data.reports.flatMap((raw) => {
      const value = record(raw);
      return typeof value.kind === "string" ? [{
        kind: value.kind, found: Number(value.found) || 0,
        eligible: Number(value.eligible) || 0, excluded: Number(value.excluded) || 0,
      }] : [];
    }),
    unsupportedKinds: Array.isArray(data.unsupported_kinds)
      ? data.unsupported_kinds.filter((k): k is string => typeof k === "string") : [],
  };
}
