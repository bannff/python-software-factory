import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export const MIGRATION_KINDS = ["memory", "lessons", "schedules", "markdown"] as const;
export type MigrationKind = (typeof MIGRATION_KINDS)[number];

export interface MigrationReport {
  kind: string;
  found: number;
  eligible: number;
  excluded: number;
}

export interface MigrationSample {
  kind: string;
  sample: string;
}

export interface MigrationPreview {
  planDigest: string;
  status: string;
  reports: MigrationReport[];
  samples: MigrationSample[];
}

export interface MigrationProgress {
  kind: string;
  imported: number;
  skipped: number;
  failed: number;
  cursor: number;
}

export interface MigrationRun {
  runId: string;
  status: string;
  progress: MigrationProgress[];
  terminalReason: string;
}

function record(raw: unknown): Record<string, unknown> {
  if (!raw || typeof raw !== "object") throw new Error("Migration returned invalid data.");
  return raw as Record<string, unknown>;
}

// Includes companion-x-v1 bundle kinds (kb/preferences) alongside the
// kirocrew-v1 set, so a bundle-import run's progress is never silently
// dropped even before kb/preferences import targets exist — the parser
// stays correct ahead of that follow-up landing.
const ALL_KINDS = [...MIGRATION_KINDS, "kb", "preferences"] as const;

function kind(raw: unknown): string | null {
  return typeof raw === "string" && (ALL_KINDS as readonly string[]).includes(raw) ? raw : null;
}

function finite(raw: unknown): number {
  return typeof raw === "number" && Number.isFinite(raw) && raw >= 0 ? raw : 0;
}

export async function previewMigration(kinds: MigrationKind[]): Promise<MigrationPreview> {
  const data = record(unwrapToolData(await callTool("migration_preview", {
    source: "kirocrew-v1", kinds,
  })));
  if (typeof data.plan_digest !== "string" || !Array.isArray(data.reports)) {
    throw new Error("Migration preview is unavailable.");
  }
  return {
    planDigest: data.plan_digest,
    status: typeof data.status === "string" ? data.status : "planned",
    reports: data.reports.flatMap((raw) => {
      const value = record(raw); const parsedKind = kind(value.kind);
      return parsedKind ? [{ kind: parsedKind, found: finite(value.found),
        eligible: finite(value.eligible), excluded: finite(value.excluded) }] : [];
    }),
    samples: Array.isArray(data.samples) ? data.samples.flatMap((raw) => {
      const value = record(raw); const parsedKind = kind(value.kind);
      return parsedKind && typeof value.sample === "string"
        ? [{ kind: parsedKind, sample: value.sample }] : [];
    }) : [],
  };
}

export async function startMigration(
  preview: { planDigest: string }, kinds: string[], source: "kirocrew-v1" | "companion-x-v1" = "kirocrew-v1",
): Promise<MigrationRun> {
  const data = record(unwrapToolData(await callTool("migration_start", {
    plan_digest: preview.planDigest, kinds, source,
  })));
  if (typeof data.run_id !== "string" || typeof data.status !== "string") {
    throw new Error("Migration did not start.");
  }
  return { runId: data.run_id, status: data.status, progress: [], terminalReason: "" };
}

export async function getMigration(runId: string): Promise<MigrationRun> {
  const data = record(unwrapToolData(await callTool("migration_get", { run_id: runId })));
  if (typeof data.run_id !== "string" || typeof data.status !== "string"
      || !Array.isArray(data.progress)) throw new Error("Migration progress is unavailable.");
  return {
    runId: data.run_id,
    status: data.status,
    terminalReason: typeof data.terminal_reason === "string" ? data.terminal_reason : "",
    progress: data.progress.flatMap((raw) => {
      const value = record(raw); const parsedKind = kind(value.kind);
      return parsedKind ? [{ kind: parsedKind, imported: finite(value.imported),
        skipped: finite(value.skipped), failed: finite(value.failed), cursor: finite(value.cursor) }] : [];
    }),
  };
}
