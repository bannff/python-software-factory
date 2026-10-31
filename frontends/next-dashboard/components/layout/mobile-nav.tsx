"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { syncCanvasRoute } from "@/lib/canvas-routes";
import { CAPABILITY_VIEWS, NAV_GROUPS } from "./activity-bar";
import type { CanvasViewId } from "@/lib/types";

/**
 * Mobile navigation (below `md`). The 48px desktop rail is hidden at this
 * breakpoint; this ≥44px named control opens an accessible labeled sheet that
 * groups the exact ``NAV_GROUPS``. Selecting a destination navigates through
 * the same ``syncCanvasRoute`` + ``onViewChange`` path the rail uses and closes
 * the sheet. Radix Dialog supplies the focus trap, Esc-to-close, and
 * return-focus. Hidden entirely at `md` and up, so desktop is unchanged.
 */
export function MobileNav({ activeView, onViewChange }: {
  activeView: CanvasViewId;
  onViewChange: (view: CanvasViewId) => void;
}) {
  const [open, setOpen] = useState(false);

  const select = (id: CanvasViewId) => {
    syncCanvasRoute(id);
    onViewChange(id);
    setOpen(false);
  };

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <div className="flex h-11 items-center gap-2 border-b border-border/50 bg-card/20 px-2 md:hidden">
        <Dialog.Trigger asChild>
          <button
            type="button"
            aria-label="Open navigation menu"
            className="flex h-11 w-11 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Menu className="h-5 w-5" />
          </button>
        </Dialog.Trigger>
        <span className="text-sm font-medium">Menu</span>
      </div>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[100] bg-black/40 backdrop-blur-sm md:hidden" />
        <Dialog.Content className="fixed inset-y-0 left-0 z-[100] flex w-72 max-w-[80vw] flex-col gap-4 overflow-y-auto border-r border-border/50 bg-card p-4 shadow-xl focus:outline-none md:hidden">
          <Dialog.Title className="text-sm font-semibold">Navigate</Dialog.Title>
          <Dialog.Description className="sr-only">
            Choose a destination. The menu closes when you pick one.
          </Dialog.Description>
          {NAV_GROUPS.map((group) => (
            <div
              key={group.caption}
              role="group"
              aria-label={group.caption}
              className="flex flex-col gap-1"
            >
              <p className="px-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                {group.caption}
              </p>
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = activeView === item.id
                  || (item.id === "capabilities" && CAPABILITY_VIEWS.has(activeView));
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => select(item.id)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex min-h-11 items-center gap-3 rounded-md px-3 text-sm transition-colors",
                      active
                        ? "bg-violet-500/15 text-violet-300"
                        : "text-foreground hover:bg-accent/50",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {item.label}
                  </button>
                );
              })}
            </div>
          ))}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
