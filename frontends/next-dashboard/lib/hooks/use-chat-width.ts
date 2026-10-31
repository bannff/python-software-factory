"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "companion-x:chat-width";
export const CHAT_MIN_WIDTH = 440;
export const CHAT_DEFAULT_WIDTH = 440;

/** Maximum width as a fraction of the viewport — leaves room for canvas + activity bar. */
const CHAT_MAX_FRACTION = 0.7;

function clampWidth(value: number, viewportWidth: number): number {
  const max = Math.max(CHAT_MIN_WIDTH, Math.floor(viewportWidth * CHAT_MAX_FRACTION));
  return Math.min(max, Math.max(CHAT_MIN_WIDTH, Math.round(value)));
}

/**
 * Owns the chat sidebar width.
 *
 * - Persists to localStorage so the user's preferred width survives reloads.
 * - Clamps to [440, 70% of viewport] on every set and on viewport resize.
 * - Returns a stable `setWidth` callback safe to pass to mousemove handlers.
 */
export function useChatWidth() {
  const [width, setWidthState] = useState<number>(CHAT_DEFAULT_WIDTH);

  // Hydrate from localStorage after mount (avoids SSR mismatch).
  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    const parsed = stored ? Number(stored) : NaN;
    if (Number.isFinite(parsed)) {
      setWidthState(clampWidth(parsed, window.innerWidth));
    }
  }, []);

  // Re-clamp on viewport resize so a stale wide width doesn't push canvas off-screen.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const onResize = () => setWidthState((w) => clampWidth(w, window.innerWidth));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const setWidth = useCallback((next: number) => {
    if (typeof window === "undefined") return;
    const clamped = clampWidth(next, window.innerWidth);
    setWidthState(clamped);
    window.localStorage.setItem(STORAGE_KEY, String(clamped));
  }, []);

  return { width, setWidth };
}
