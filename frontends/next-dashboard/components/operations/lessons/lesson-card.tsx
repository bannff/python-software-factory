"use client";

import { categoryLabel, scopeLabel, sourceLabel, statusLabel, statusTone } from "./lesson-language";
import type { Lesson } from "./lesson-types";

const TONE: Record<ReturnType<typeof statusTone>, string> = {
  ok: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  info: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  warn: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  muted: "border-border/60 bg-muted/50 text-muted-foreground",
};

/** One selectable lesson in the list column. Plain language only. */
export function LessonCard({
  lesson,
  active,
  onOpen,
}: {
  lesson: Lesson;
  active: boolean;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-current={active}
      className={`group w-full rounded-xl border p-4 text-left transition-all hover:border-violet-500/40 hover:bg-card/60 ${
        active ? "border-violet-500/50 bg-violet-500/[0.06]" : "border-border/60 bg-card/30"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="line-clamp-2 text-sm font-medium">{lesson.rule}</p>
        <span
          className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium ${TONE[statusTone(lesson.status)]}`}
        >
          {statusLabel(lesson.status)}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-1 text-[10px] text-muted-foreground">
        <span className="rounded-full bg-muted/60 px-2 py-0.5">{categoryLabel(lesson.category)}</span>
        <span className="rounded-full bg-muted/60 px-2 py-0.5">{scopeLabel(lesson)}</span>
        <span className="rounded-full bg-muted/60 px-2 py-0.5">{sourceLabel(lesson.source)}</span>
      </div>
    </button>
  );
}
