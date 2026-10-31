"use client";

import { InboxPopover } from "./inbox-popover";

export function Topbar() {
  return (
    <header className="flex h-10 items-center justify-between border-b border-border/50 bg-card/30 backdrop-blur-md px-4">
      <div className="flex items-center gap-2.5">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-violet-500 to-indigo-600 shadow-sm">
          <span className="text-[10px] font-bold text-white">X</span>
        </div>
        <span className="text-sm font-semibold tracking-tight">Companion X</span>
      </div>
      <InboxPopover />
    </header>
  );
}
