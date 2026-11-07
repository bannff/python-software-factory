"use client";

import { useEffect, useRef, useState } from "react";
import { ConfirmDelete } from "@/components/ui/confirm-delete";
import { Ban, Check, Loader2, Trash2 } from "lucide-react";
import {
  acceptLesson,
  fetchLesson,
  LESSON_CONFLICT_MESSAGE,
  rejectLesson,
  lessonActionFailure,
  onlyRevisionDrifted,
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

  /** Run ``action`` against ``target``; on failure reconcile with the server, retrying once on revision-only drift. */
  const attempt = async (action: (target: Lesson) => Promise<void>, target: Lesson, canRetry: boolean) => {
    try {
      await action(target);
    } catch (error) {
      let current: Lesson;
      try {
        current = await fetchLesson(lesson.lessonId);
      } catch {
        onRemoved(lesson.lessonId);
        return;
      }
      if (canRetry && onlyRevisionDrifted(target, current)) {
        await attempt(action, current, false);
      } else if (current.revision !== lesson.revision || current.status !== lesson.status) {
        // Only a lesson that actually moved on is a conflict; otherwise the action itself failed.
        setNotice(LESSON_CONFLICT_MESSAGE);
        onChanged();
      } else {
        setNotice(lessonActionFailure(error));
      }
    }
  };

  const run = async (action: (target: Lesson) => Promise<void>) => {
    setBusy(true);
    setNotice(null);
    try {
      await attempt(action, lesson, true);
    } finally {
      setBusy(false);
    }
  };

  const accept = () => run(async (l) => { await acceptLesson(l, sessionId); onChanged(); });
  const reject = () => run(async (l) => { await rejectLesson(l, sessionId); onChanged(); });
  const remove = () => run(async (l) => { await removeLesson(l, sessionId); onRemoved(l.lessonId); });

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
        <ConfirmDelete
          label="Delete lesson" disabled={busy} onConfirm={() => void remove()}
          className="inline-flex items-center gap-1.5 rounded-md border border-destructive/40 px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10 disabled:opacity-50"
        >
          <Trash2 className="h-3.5 w-3.5" /> Delete
        </ConfirmDelete>
      </div>
    </article>
  );
}
