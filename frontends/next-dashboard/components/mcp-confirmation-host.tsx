"use client";

import { useEffect, useSyncExternalStore } from "react";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { ShieldCheck } from "lucide-react";

import {
  cancelAllConfirmations,
  getConfirmationSnapshot,
  resolveConfirmation,
  subscribeConfirmations,
} from "@/lib/mcp-confirmation";

/** Global host for MCP v2 form-confirmation elicitation. */
export function McpConfirmationHost() {
  const request = useSyncExternalStore(
    subscribeConfirmations,
    getConfirmationSnapshot,
    () => null,
  );

  useEffect(() => cancelAllConfirmations, []);

  return (
    <AlertDialog.Root
      open={request !== null}
      onOpenChange={(open) => {
        if (!open && request) resolveConfirmation("cancel");
      }}
    >
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-[100] bg-black/55 backdrop-blur-sm" />
        <AlertDialog.Content
          data-testid="mcp-confirmation-dialog"
          className="fixed left-1/2 top-1/2 z-[101] w-[min(92vw,440px)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-violet-400/25 bg-background/95 p-5 shadow-2xl"
        >
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-violet-500/10 p-2 text-violet-400">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <AlertDialog.Title className="text-sm font-semibold">
                Confirm MCP operation
              </AlertDialog.Title>
              <AlertDialog.Description className="mt-1.5 text-sm leading-6 text-muted-foreground">
                {request?.message ?? "This operation requires confirmation."}
              </AlertDialog.Description>
              {request && (
                <p className="mt-2 text-[11px] text-muted-foreground/70">
                  Confirmation field: <code>{request.field}</code>
                </p>
              )}
            </div>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              data-testid="mcp-confirmation-deny"
              onClick={() => resolveConfirmation("decline")}
              className="rounded-lg border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-accent"
            >
              Deny
            </button>
            <button
              type="button"
              data-testid="mcp-confirmation-approve"
              onClick={() => resolveConfirmation("accept")}
              className="rounded-lg bg-violet-600 px-3 py-2 text-sm font-medium text-white hover:bg-violet-500"
            >
              Approve
            </button>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
