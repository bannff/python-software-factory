"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface PopoverProps {
  trigger: React.ReactNode;
  children: React.ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
}

/**
 * Minimal popover — opens upward from the status bar on click.
 * No Radix dependency; just a controlled div with click-outside handling.
 */
export function Popover({ trigger, children, align = "left", className }: PopoverProps) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 hover:text-foreground transition-colors cursor-pointer"
      >
        {trigger}
      </button>
      {open && (
        <div
          className={cn(
            "absolute bottom-7 z-50 min-w-[220px] rounded-lg border border-border/50 bg-card/95 backdrop-blur-xl p-3 shadow-xl text-xs",
            align === "left" && "left-0",
            align === "right" && "right-0",
            align === "center" && "left-1/2 -translate-x-1/2",
            className,
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}
