import { callTool } from "@/lib/api";
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
export const LESSON_REMOVED_MESSAGE =
  "This lesson is no longer here — it was already removed.";
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
  await callTool("lessons_remove", {
    lesson_id: lesson.lessonId,
    expected_revision: lesson.revision, envelope: { session_id: sessionId },
  });
}
