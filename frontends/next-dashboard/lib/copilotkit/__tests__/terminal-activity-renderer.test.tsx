import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { getTerminalSessions, resetTerminalSessions } from "@/lib/terminal-store";

import { terminalActivityRenderer } from "../terminal-activity-renderer";

describe("terminal activity renderer", () => {
  beforeEach(resetTerminalSessions);
  const content = {
    activityType: "terminal.command" as const,
    run_id: "cmd_123",
    status: "completed" as const,
    command: "pytest",
    cwd: "src",
    stdout: "2 passed\n",
    stderr: "",
    started_at: 1,
    completed_at: 2,
    exit_code: 0,
    duration_ms: 25,
    truncated: false,
  };

  it("registers the exact terminal.command activity type", () => {
    expect(terminalActivityRenderer.activityType).toBe("terminal.command");
    expect(terminalActivityRenderer.content.parse(content)).toEqual(content);
  });

  it("rejects unbounded or unknown activity shapes", () => {
    expect(terminalActivityRenderer.content.safeParse({
      ...content, activityType: "subagent.single",
    }).success).toBe(false);
    expect(terminalActivityRenderer.content.safeParse({
      ...content, secret: "unexpected",
    }).success).toBe(false);
  });

  it("renders the chat card and projects the command into the dock", () => {
    render(terminalActivityRenderer.render({ content }));
    expect(screen.getByText("Terminal · pytest")).toBeTruthy();
    expect(getTerminalSessions()).toEqual([content]);
  });
});
