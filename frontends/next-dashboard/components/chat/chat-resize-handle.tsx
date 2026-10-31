"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface ChatResizeHandleProps {
  /** Called continuously during drag with the desired sidebar width in px. */
  onResize: (nextWidth: number) => void;
}

/**
 * 4px drag gutter on the left edge of the chat sidebar.
 *
 * The chat panel is anchored to the right side of the viewport, so dragging the
 * handle leftward should *grow* the panel. We compute the new width as
 * `viewport.right - pointer.x`. The handle widens to 6px and turns violet on
 * hover/drag for affordance, matching VS Code's resize gutter pattern.
 */
export function ChatResizeHandle({ onResize }: ChatResizeHandleProps) {
  const [dragging, setDragging] = useState(false);
  // Hold the latest callback in a ref so move/up listeners don't restart.
  const onResizeRef = useRef(onResize);
  onResizeRef.current = onResize;

  const startDrag = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  useEffect(() => {
    if (!dragging) return;

    const onMove = (e: PointerEvent) => {
      const next = window.innerWidth - e.clientX;
      onResizeRef.current(next);
    };
    const stop = () => setDragging(false);

    // Lock cursor + suppress text selection across the whole document while dragging.
    const prevCursor = document.body.style.cursor;
    const prevSelect = document.body.style.userSelect;
    document.body.style.cursor = "ew-resize";
    document.body.style.userSelect = "none";

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
      document.body.style.cursor = prevCursor;
      document.body.style.userSelect = prevSelect;
    };
  }, [dragging]);

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize chat panel"
      onPointerDown={startDrag}
      className={cn(
        "absolute inset-y-0 -left-0.5 z-20 w-1 cursor-ew-resize",
        "transition-colors duration-150",
        "hover:bg-violet-500/40",
        dragging && "bg-violet-500/60",
      )}
    />
  );
}
