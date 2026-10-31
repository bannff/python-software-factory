import { unwrapToolData } from "@/lib/tool-result-data";

/**
 * Client view of a typed Lessons record (M7 Operations surface).
 *
 * Mirrors the read-safe subset of the Lessons brick ``LessonRecord`` returned
 * by ``lessons_list`` / ``lessons_get`` / ``lessons_accept`` / ``lessons_reject``.
 * Identity fields (tenant/owner/identity_key) are never modelled here — the UI
 * is ambient-authorized and passes no identity args. Every row is parsed
 * defensively so a degraded or partial record is dropped, never crashes.
 */
export type LessonStatus = "proposed" | "accepted" | "rejected" | "superseded";
export type LessonScope = "global" | "persona";
export type LessonSource = "user_explicit" | "feedback" | "outcome" | "import";
export type LessonCategory = "tool" | "preference" | "knowledge";

export interface Lesson {
  lessonId: string;
  rule: string;
  negative: string | null;
  category: LessonCategory;
  scope: LessonScope;
  scopeId: string | null;
  source: LessonSource;
  evidence: string[];
  status: LessonStatus;
  revision: number;
  updatedAt: string;
}

const LESSON_ID = /^les_[0-9a-f]{32}$/;
const STATUSES = ["proposed", "accepted", "rejected", "superseded"] as const;
const SCOPES = ["global", "persona"] as const;
const SOURCES = ["user_explicit", "feedback", "outcome", "import"] as const;
const CATEGORIES = ["tool", "preference", "knowledge"] as const;

function oneOf<T extends readonly string[]>(list: T, value: unknown): T[number] | null {
  return typeof value === "string" && (list as readonly string[]).includes(value)
    ? (value as T[number])
    : null;
}

function nonBlank(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

/** Parse one raw row into a Lesson, or null if it is not a valid record. */
export function parseLessonRow(row: unknown): Lesson | null {
  if (!row || typeof row !== "object") return null;
  const r = row as Record<string, unknown>;
  const status = oneOf(STATUSES, r.status);
  const scope = oneOf(SCOPES, r.scope);
  const source = oneOf(SOURCES, r.source);
  const category = oneOf(CATEGORIES, r.category);
  if (typeof r.lesson_id !== "string" || !LESSON_ID.test(r.lesson_id)) return null;
  if (nonBlank(r.rule) === null) return null;
  if (!status || !scope || !source || !category) return null;
  if (!Number.isInteger(r.revision)) return null;
  return {
    lessonId: r.lesson_id,
    rule: r.rule as string,
    negative: nonBlank(r.negative),
    category,
    scope,
    scopeId: typeof r.scope_id === "string" ? r.scope_id : null,
    source,
    evidence: Array.isArray(r.evidence)
      ? r.evidence.filter((e): e is string => typeof e === "string" && e.trim() !== "")
      : [],
    status,
    revision: r.revision as number,
    updatedAt: typeof r.updated_at === "string" ? r.updated_at : "",
  };
}

/** Unwrap + validate a ``lessons_list`` ToolResult into an ordered list. */
export function parseLessons(raw: unknown): Lesson[] {
  const data = unwrapToolData(raw);
  const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  const rows = Array.isArray(obj.lessons) ? obj.lessons : [];
  return rows.map(parseLessonRow).filter((row): row is Lesson => row !== null);
}

/** Unwrap + validate a single-lesson ToolResult (get/accept/reject). */
export function parseLesson(raw: unknown): Lesson {
  const data = unwrapToolData(raw);
  const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  const lesson = parseLessonRow(obj.lesson);
  if (!lesson) throw new Error("Lesson record unavailable");
  return lesson;
}
