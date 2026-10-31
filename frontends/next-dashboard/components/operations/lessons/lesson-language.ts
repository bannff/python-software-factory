import type {
  Lesson,
  LessonCategory,
  LessonScope,
  LessonSource,
  LessonStatus,
} from "./lesson-types";

/**
 * Plain-language mappers. The user is a product person, not an engineer, so
 * every enum becomes a short human label plus a one-line explanation. No raw
 * codes (``user_explicit``, ``proposed``, ``les_…``) ever reach the screen.
 */

type Tone = "ok" | "warn" | "muted" | "info";

const STATUS: Record<LessonStatus, { label: string; help: string; tone: Tone }> = {
  proposed: {
    label: "Suggested",
    help: "Companion X suggested this — it is waiting for you to keep or dismiss it.",
    tone: "info",
  },
  accepted: {
    label: "Active",
    help: "This lesson is active and shapes how Companion X works for you.",
    tone: "ok",
  },
  rejected: {
    label: "Dismissed",
    help: "You dismissed this suggestion, so Companion X does not follow it.",
    tone: "muted",
  },
  superseded: {
    label: "Replaced",
    help: "A newer lesson replaced this one.",
    tone: "warn",
  },
};

const SCOPE: Record<LessonScope, string> = {
  global: "Applies everywhere",
  persona: "Applies to one assistant",
};

const SOURCE: Record<LessonSource, string> = {
  user_explicit: "You taught this",
  feedback: "Learned from your feedback",
  outcome: "Learned from an outcome",
  import: "Imported from KiroCrew",
};

const CATEGORY: Record<LessonCategory, string> = {
  tool: "Tool use",
  preference: "Preference",
  knowledge: "Knowledge",
};

export function statusLabel(status: LessonStatus): string {
  return STATUS[status].label;
}

export function statusHelp(status: LessonStatus): string {
  return STATUS[status].help;
}

export function statusTone(status: LessonStatus): Tone {
  return STATUS[status].tone;
}

export function scopeLabel(lesson: Lesson): string {
  if (lesson.scope === "persona" && lesson.scopeId) {
    return `Applies to the “${lesson.scopeId}” assistant`;
  }
  return SCOPE[lesson.scope];
}

export function sourceLabel(source: LessonSource): string {
  return SOURCE[source];
}

export function categoryLabel(category: LessonCategory): string {
  return CATEGORY[category];
}
