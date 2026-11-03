import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { FindingState, STATE_LABELS } from "../finding-state";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
beforeEach(() => { callTool.mockReset(); });

describe("FindingState", () => {
  it("labels the oracle states in plain words", () => {
    expect(STATE_LABELS).toEqual({ candidate: "Open", verifying: "Verifying", verified: "Confirmed", refuted: "Dismissed" });
    render(<FindingState findingId="f1" state="candidate" />);
    expect(screen.getByRole("button", { name: "Open" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("sets the chosen state through graph_set_finding_state", async () => {
    callTool.mockResolvedValue(ok({ finding_id: "f1", state: "verified" }));
    render(<FindingState findingId="f1" state="candidate" />);
    fireEvent.click(screen.getByRole("button", { name: "Confirmed" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("graph_set_finding_state", { finding_id: "f1", state: "verified" }));
  });

  it("reports a failure instead of pretending it worked", async () => {
    callTool.mockImplementation(async () => { throw Object.assign(new Error("finding_not_found"), { reason: "finding_not_found" }); });
    render(<FindingState findingId="f1" state="candidate" />);
    fireEvent.click(screen.getByRole("button", { name: "Dismissed" }));
    expect((await screen.findByRole("alert")).textContent).toContain("finding_not_found");
  });
});
