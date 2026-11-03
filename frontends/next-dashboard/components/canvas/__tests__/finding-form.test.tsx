import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { FindingForm } from "../finding-form";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
beforeEach(() => { callTool.mockReset(); });

describe("FindingForm", () => {
  it("requires a title before sending anything", () => {
    render(<FindingForm kinds={[]} onDone={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Save finding" }));
    expect(screen.getByRole("alert").textContent).toMatch(/title/i);
    expect(callTool).not.toHaveBeenCalled();
  });

  it("records a finding of any kind", async () => {
    callTool.mockResolvedValue(ok({ finding_id: "f9", state: "candidate" }));
    const onDone = vi.fn();
    render(<FindingForm kinds={["security"]} onDone={onDone} />);
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Slow query" } });
    fireEvent.change(screen.getByLabelText("Severity"), { target: { value: "medium" } });
    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "performance" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "p95 3s" } });
    fireEvent.click(screen.getByRole("button", { name: "Save finding" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("graph_record_finding",
      { title: "Slow query", severity: "medium", kind: "performance", description: "p95 3s" }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it("shows the server's reason when saving fails", async () => {
    callTool.mockImplementation(async () => { throw Object.assign(new Error("finding_invalid"), { reason: "finding_invalid" }); });
    render(<FindingForm kinds={[]} onDone={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Save finding" }));
    expect((await screen.findByRole("alert")).textContent).toContain("finding_invalid");
  });
});
