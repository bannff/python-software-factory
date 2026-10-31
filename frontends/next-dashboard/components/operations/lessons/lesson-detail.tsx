"use client";

import { useEffect, useRef, useState } from "react";
import { Ban, Check, Loader2, Trash2 } from "lucide-react";
import {
  acceptLesson,
  fetchLesson,
  LESSON_CONFLICT_MESSAGE,
  rejectLesson,
  removeLesson,
} from "./lesson-actions";
import {
  categoryLabel,
  scopeLabel,
  sourceLabel,
  statusHelp,
  statusLabel,
} from "./lesson-language";
import type { Lesson } from "./lesson-types";

/**
 * Focused detail for one lesson. Shows status/scope/source/rule/negative in
 * plain language and offers only the curation moves the lifecycle supports.
 * A failed action reconciles against the server: gone → removed, else the
 * refreshed record with a conflict notice. The heading is programmatically
 * focusable so a deep-link (``focusLessonId``) lands the caret here.
 */
export function LessonDetail({
  lesson,
  sessionId,
  autoFocus,
  onFocused,
  onChanged,
  onRemoved,
  onClose,
}: {
  lesson: Lesson;
  sessionId: string;
  autoFocus?: boolean;
  onFocused?: () => void;
  onChanged: () => void;
  onRemoved: (lessonId: string) => void;
  onClose: () => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (autoFocus) {
      headingRef.current?.focus();
      onFocused?.();
    }
  }, [autoFocus, lesson.lessonId, onFocused]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setNotice(null);
    try {
      await action();
    } catch {
      try {
        await fetchLesson(lesson.lessonId);
        setNotice(LESSON_CONFLICT_MESSAGE);
        onChanged();
      } catch {
        onRemoved(lesson.lessonId);
      }
    } finally {
      setBusy(false);
    }
  };

  const accept = () => run(async () => { await acceptLesson(lesson, sessionId); onChanged(); });
  const reject = () => run(async () => { await rejectLesson(lesson, sessionId); onChanged(); });
  const remove = () => run(async () => { await removeLesson(lesson, sessionId); onRemoved(lesson.lessonId); });

  const curatable = lesson.status === "proposed";

  return (
    <article className="rounded-xl border border-violet-500/30 bg-violet-500/[0.04] p-5" aria-labelledby="lesson-heading">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-muted-foreground">{statusLabel(lesson.status)} · {categoryLabel(lesson.category)}</p>
          <h2 id="lesson-heading" ref={headingRef} tabIndex={-1} className="mt-1 text-lg font-semibold outline-none">
            {lesson.rule}
          </h2>
        </div>
        <button type="button" onClick={onClose} className="shrink-0 text-xs text-muted-foreground hover:text-foreground">
          Close
        </button>
      </div>

      <p className="text-sm text-muted-foreground">{statusHelp(lesson.status)}</p>

      {lesson.negative && (
        <div className="mt-4 rounded-lg border border-border/60 bg-card/40 p-3">
          <p className="text-xs font-medium text-muted-foreground">What to avoid</p>
          <p className="mt-1 text-sm">{lesson.negative}</p>
        </div>
      )}

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div><dt className="text-xs text-muted-foreground">Where it applies</dt><dd>{scopeLabel(lesson)}</dd></div>
        <div><dt className="text-xs text-muted-foreground">How it was learned</dt><dd>{sourceLabel(lesson.source)}</dd></div>
      </dl>

      {lesson.evidence.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-medium text-muted-foreground">Evidence</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {lesson.evidence.map((item, index) => <li key={index}>{item}</li>)}
          </ul>
        </div>
      )}

      {notice && (
        <div role="alert" className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">
          {notice}
        </div>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        {curatable && (
          <>
            <button type="button" onClick={accept} disabled={busy} className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-50">
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />} Keep lesson
            </button>
            <button type="button" onClick={reject} disabled={busy} className="inline-flex items-center gap-1.5 rounded-md border border-border/60 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted/50 disabled:opacity-50">
              <Ban className="h-3.5 w-3.5" /> Dismiss
            </button>
          </>
        )}
        <button type="button" onClick={remove} disabled={busy} className="inline-flex items-center gap-1.5 rounded-md border border-destructive/40 px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10 disabled:opacity-50">
          <Trash2 className="h-3.5 w-3.5" /> Delete
        </button>
      </div>
    </article>
  );
}
