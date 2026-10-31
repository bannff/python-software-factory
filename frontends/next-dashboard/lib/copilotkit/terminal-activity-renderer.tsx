"use client";

import { useEffect } from "react";
import { Terminal } from "lucide-react";
import { z } from "zod";

import { recordTerminalSession } from "@/lib/terminal-store";
import { ToolCallCard } from "./tool-call-card";

const TerminalContent = z.object({
  activityType: z.literal("terminal.command"),
  run_id: z.string(),
  status: z.enum(["running", "completed", "failed", "cancelled", "timed_out"]),
  command: z.string(),
  cwd: z.string(),
  stdout: z.string(),
  stderr: z.string(),
  started_at: z.number(),
  completed_at: z.number().nullable().optional(),
  exit_code: z.number().nullable().optional(),
  duration_ms: z.number().nullable().optional(),
  truncated: z.boolean(),
}).strict();

type TerminalRow = z.infer<typeof TerminalContent>;

function summary(content: TerminalRow) {
  if (content.status === "running") return content.cwd;
  if (content.status === "cancelled") return "Cancelled";
  if (content.status === "timed_out") return "Timed out";
  return `Exit ${content.exit_code ?? "?"}${content.truncated ? " · truncated" : ""}`;
}

function TerminalActivity({ content }: { content: TerminalRow }) {
  useEffect(() => { recordTerminalSession(content); }, [content]);
  const output = [content.stdout, content.stderr].filter(Boolean).join("\n");
  return (
    <ToolCallCard
      name="devtools_run_command"
      title={`Terminal · ${content.command || "command"}`}
      status={content.status === "running" ? "executing" : "complete"}
      icon={<Terminal className="h-3.5 w-3.5" />}
      previewLine={summary(content)}
    >
      <div className="space-y-2">
        <div className="font-mono text-[10px] text-muted-foreground">{content.cwd}</div>
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted/50 p-3 font-mono text-[11px] leading-4 text-foreground/90">
          {output || "Waiting for output…"}
        </pre>
      </div>
    </ToolCallCard>
  );
}

export const terminalActivityRenderer = {
  activityType: "terminal.command" as const,
  content: TerminalContent,
  render: ({ content }: { content: TerminalRow }) => <TerminalActivity content={content} />,
};
