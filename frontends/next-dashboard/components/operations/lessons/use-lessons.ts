"use client";

import { useCallback, useEffect, useState } from "react";
import { callTool } from "@/lib/api";
import { parseLessons, type Lesson } from "./lesson-types";
import { LESSON_LIST_ERROR } from "./lesson-actions";

/**
 * Read the caller's owner-scoped Lessons via the real ``lessons_list`` MCP
 * tool (ambient auth, no identity args). A failure degrades to a truthful
 * error string so the view can render retry — never a fake empty list.
 */
export function useLessons() {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setLessons(parseLessons(await callTool("lessons_list", {})));
      setError(null);
    } catch {
      setError(LESSON_LIST_ERROR);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { lessons, loading, error, refresh };
}
