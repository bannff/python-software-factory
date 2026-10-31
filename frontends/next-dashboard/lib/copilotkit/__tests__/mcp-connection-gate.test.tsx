import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  status: "connecting" as "idle" | "connecting" | "connected" | "error",
  error: null as string | null,
  retry: vi.fn(),
}));

vi.mock("@/lib/hooks/use-mcp-connection", () => ({
  useMcpConnection: () => ({
    status: mocks.status,
    ready: mocks.status === "connected",
    error: mocks.error,
    retry: mocks.retry,
  }),
}));
vi.mock("@copilotkit/react-core/v2", () => ({
  CopilotChatInput: {
    TextArea: (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...props} />,
    SendButton: (props: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button {...props} />,
  },
}));

import { McpConnectionNotice, McpReadyTextArea } from "../mcp-connection-gate";
import { StopAwareSendButton } from "../stop-button";

beforeEach(() => {
  mocks.status = "connecting";
  mocks.error = null;
  mocks.retry.mockReset();
});

describe("MCP connection composer gate", () => {
  it("disables input and normal send while the handshake is pending", () => {
    render(<><McpReadyTextArea /><StopAwareSendButton /></>);
    expect(screen.getByPlaceholderText("Connecting to tools…")).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "Connecting to tools" })).toHaveProperty("disabled", true);
  });

  it("enables the native input and send contract after connection", () => {
    mocks.status = "connected";
    render(<><McpReadyTextArea placeholder="Ask anything…" />
      <StopAwareSendButton disabled={false} /></>);
    expect(screen.getByPlaceholderText("Ask anything…")).toHaveProperty("disabled", false);
    expect(screen.getByRole("button", { name: "Send message" })).toHaveProperty("disabled", false);
  });

  it("shows a truthful failure with retry and keeps input disabled", () => {
    mocks.status = "error";
    render(<><McpConnectionNotice /><McpReadyTextArea /></>);
    expect(screen.getByRole("alert").textContent).toContain("Tools unavailable");
    expect(screen.getByPlaceholderText(/Tools unavailable/)).toHaveProperty("disabled", true);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(mocks.retry).toHaveBeenCalledOnce();
  });

  it("renders the underlying cause instead of a generic failure string", () => {
    mocks.status = "error";
    mocks.error = "Local MCP authentication failed for http://localhost:3000/mcp.";
    render(<McpConnectionNotice />);

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("Local MCP authentication failed for http://localhost:3000/mcp.");
    expect(screen.getByTitle(mocks.error)).toBeTruthy();
  });

  it("keeps CopilotKit stop mode available when MCP is disconnected", () => {
    render(<StopAwareSendButton disabled={false}><span>stop</span></StopAwareSendButton>);
    expect(screen.getByRole("button", { name: "Stop generating" })).toHaveProperty("disabled", false);
  });
});
