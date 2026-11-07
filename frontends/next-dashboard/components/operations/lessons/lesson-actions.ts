import { callTool } from "@/lib/api";
import { errorReason, withReason } from "@/lib/error-reason";
import { unwrapToolData } from "@/lib/tool-result-data";
import { parseLesson, type Lesson } from "./lesson-types";

/**
 * Ambient-authorized Lessons curation actions. Each call carries ``lesson_id`` + ``expected_revision`` and the active
 * ``session_id`` needed for curation verification. Tenant/owner remain ambient.
 *
 * The Lessons lifecycle only supports three curation moves today:
 *   • accept  — a Suggested lesson becomes Active   (proposed → accepted)
 *   • reject  — a Suggested lesson becomes Dismissed (proposed → rejected)
 *   • remove  — delete a lesson at any status
 * Accept/reject are valid only while the lesson is still Suggested and its
 * revision matches; the server rejects anything else as a conflict.
 */

export const LESSON_CONFLICT_MESSAGE =
  "This lesson changed since you opened it. We refreshed it to the latest — take another look.";
export const LESSON_REMOVED_MESSAGE = "This lesson has been deleted.";
export const LESSON_ACTION_FAILED = "That action didn't go through. Try again.";
export const LESSON_CHAT_UNSAVED = "Send a message first so this chat is saved, then try again.";

/** Curation needs a persisted chat thread; retrying cannot help until one message is saved. */
export function lessonActionFailure(error: unknown): string {
  const reason = errorReason(error);
  return reason === "lesson_session_not_found" ? LESSON_CHAT_UNSAVED : withReason(LESSON_ACTION_FAILED, reason);
}
export const LESSON_LIST_ERROR = "Lessons unavailable";

export async function fetchLesson(lessonId: string): Promise<Lesson> {
  return parseLesson(await callTool("lessons_get", { lesson_id: lessonId }));
}

export async function acceptLesson(lesson: Lesson, sessionId: string): Promise<Lesson> {
  return parseLesson(
    await callTool("lessons_accept", {
      lesson_id: lesson.lessonId,
      expected_revision: lesson.revision, envelope: { session_id: sessionId },
    }),
  );
}

export async function rejectLesson(lesson: Lesson, sessionId: string): Promise<Lesson> {
  return parseLesson(
    await callTool("lessons_reject", {
      lesson_id: lesson.lessonId,
      expected_revision: lesson.revision, envelope: { session_id: sessionId },
    }),
  );
}

export async function removeLesson(lesson: Lesson, sessionId: string): Promise<void> {
  // callTool resolves on a domain ok:false; unwrap so a refused delete throws instead of reading as removed.
  unwrapToolData(await callTool("lessons_remove", {
    lesson_id: lesson.lessonId,
    expected_revision: lesson.revision, envelope: { session_id: sessionId },
  }));
}
