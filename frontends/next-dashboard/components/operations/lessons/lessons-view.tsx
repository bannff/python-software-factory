"use client";

import { useEffect, useMemo, useState } from "react";
import { GraduationCap, Loader2, RefreshCw } from "lucide-react";
import { useAgent } from "@copilotkit/react-core/v2";
import { useLessons } from "./use-lessons";
import { LessonCard } from "./lesson-card";
import { LessonDetail } from "./lesson-detail";
import { LESSON_REMOVED_MESSAGE } from "./lesson-actions";

/**
 * Lessons Operations surface (M7 Option A). A responsive list-detail: the
 * lesson list on the left, a focused detail panel on the right (stacked on
 * small screens). Loading, empty, error/retry, conflict-refresh, and deleted
 * states are all truthful with plain-language copy — never a raw code.
 *
 * ``focusLessonId`` deep-links a specific lesson: the view selects it and
 * focuses the detail heading, then calls ``onFocusHandled`` exactly once.
 */
function DeletedNotice({ onBack }: { onBack: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-border/60 bg-card/30 p-5 text-sm">
      <p>{LESSON_REMOVED_MESSAGE}</p>
      <button type="button" onClick={onBack} className="mt-3 rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50">
        Back to lessons
      </button>
    </div>
  );
}

export default function LessonsView({
  focusLessonId,
  onFocusHandled,
}: {
  focusLessonId?: string;
  onFocusHandled?: () => void;
} = {}) {
  const { agent } = useAgent({ agentId: "companion_x" });
  const { lessons, loading, error, refresh } = useLessons();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusPending, setFocusPending] = useState(false);

  useEffect(() => {
    if (focusLessonId) {
      setSelectedId(focusLessonId);
      setFocusPending(true);
    }
  }, [focusLessonId]);

  const active = useMemo(
    () => lessons.find((lesson) => lesson.lessonId === selectedId) ?? null,
    [lessons, selectedId],
  );
  const deleted = selectedId !== null && !active && !loading && !error;

  const clearSelection = () => {
    setSelectedId(null);
    setFocusPending(false);
  };

  return (
    <section className="mx-auto flex min-h-full w-full max-w-7xl flex-col gap-5 p-6" aria-labelledby="lessons-title">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-400">Memory</p>
          <h1 id="lessons-title" className="mt-1 text-2xl font-semibold tracking-tight">Lessons</h1>
          <p className="mt-1 text-sm text-muted-foreground">What Companion X has learned to do — and what to avoid — for you.</p>
        </div>
        <button type="button" onClick={refresh} aria-label="Refresh lessons" className="rounded-lg border border-border/60 p-2 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <span>Lessons unavailable right now.</span>
          <button type="button" onClick={refresh} className="rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50">Retry</button>
        </div>
      )}

      {loading && lessons.length === 0 && !error && (
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading lessons…
        </div>
      )}

      {!loading && !error && lessons.length === 0 && !deleted && (
        <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-border/60 p-10 text-center">
          <GraduationCap className="h-8 w-8 text-violet-400/70" />
          <h2 className="mt-3 font-medium">No lessons yet</h2>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            When you teach Companion X something — or it learns from your feedback — the lesson shows up here for you to keep or dismiss.
          </p>
        </div>
      )}

      {!error && deleted && lessons.length === 0 && (
        <DeletedNotice onBack={clearSelection} />
      )}

      {!error && lessons.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
          <div className="flex flex-col gap-3" role="list" aria-label="Lessons">
            {lessons.map((lesson) => (
              <div role="listitem" key={lesson.lessonId}>
                <LessonCard
                  lesson={lesson}
                  active={lesson.lessonId === selectedId}
                  onOpen={() => { setSelectedId(lesson.lessonId); setFocusPending(false); }}
                />
              </div>
            ))}
          </div>
          <div className="min-w-0">
            {deleted ? (
              <DeletedNotice onBack={clearSelection} />
            ) : active ? (
              <LessonDetail
                lesson={active}
                sessionId={agent.threadId}
                autoFocus={focusPending}
                onFocused={() => { setFocusPending(false); onFocusHandled?.(); }}
                onChanged={refresh}
                onRemoved={() => refresh()}
                onClose={clearSelection}
              />
            ) : (
              <div className="flex h-full min-h-40 items-center justify-center rounded-xl border border-dashed border-border/60 p-6 text-center text-sm text-muted-foreground">
                Select a lesson to review it.
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
