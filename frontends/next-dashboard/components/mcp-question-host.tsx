"use client";

import { useEffect, useSyncExternalStore } from "react";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { HelpCircle } from "lucide-react";

import {
  answerQuestion,
  cancelAllQuestions,
  cancelQuestion,
  getQuestionSnapshot,
  subscribeQuestions,
} from "@/lib/mcp-question";

/** Global host for MCP v2 multiple-choice question elicitation. */
export function McpQuestionHost() {
  const request = useSyncExternalStore(
    subscribeQuestions,
    getQuestionSnapshot,
    () => null,
  );

  useEffect(() => cancelAllQuestions, []);

  return (
    <AlertDialog.Root
      open={request !== null}
      onOpenChange={(open) => {
        if (!open && request) cancelQuestion();
      }}
    >
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-[100] bg-black/55 backdrop-blur-sm" />
        <AlertDialog.Content
          data-testid="mcp-question-dialog"
          className="fixed left-1/2 top-1/2 z-[101] w-[min(92vw,440px)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-violet-400/25 bg-background/95 p-5 shadow-2xl"
        >
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-violet-500/10 p-2 text-violet-400">
              <HelpCircle className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <AlertDialog.Title className="text-sm font-semibold">
                {request?.message ?? "The agent has a question."}
              </AlertDialog.Title>
              <AlertDialog.Description className="mt-1.5 text-sm leading-6 text-muted-foreground">
                Choose one option to continue.
              </AlertDialog.Description>
            </div>
          </div>
          <div className="mt-4 flex flex-col gap-2">
            {request?.options.map((option) => (
              <button
                key={option}
                type="button"
                data-testid={`mcp-question-option-${option}`}
                onClick={() => answerQuestion(option)}
                className="rounded-lg border border-border px-3 py-2 text-left text-sm hover:border-violet-400/50 hover:bg-violet-500/10"
              >
                {option}
              </button>
            ))}
          </div>
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              data-testid="mcp-question-cancel"
              onClick={() => cancelQuestion()}
              className="rounded-lg border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-accent"
            >
              Cancel
            </button>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
