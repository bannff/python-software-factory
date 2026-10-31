import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ get: vi.fn(), list: vi.fn(), update: vi.fn() }));
vi.mock("../approval-policy-api", () => ({
  getApprovalPolicy: (...args: unknown[]) => mocks.get(...args),
  listApprovalToolNames: (...args: unknown[]) => mocks.list(...args),
  updateApprovalPolicy: (...args: unknown[]) => mocks.update(...args),
}));
import SecuritySettingsPanel from "../security-settings-panel";

beforeEach(() => {
  mocks.get.mockReset().mockResolvedValue({ toolNames: [], revision: 0 });
  mocks.list.mockReset().mockResolvedValue([
    "devtools_read_file", "devtools_run_command", "memory_retrieve",
  ]);
  mocks.update.mockReset().mockResolvedValue({
    toolNames: ["devtools_run_command"], revision: 1,
  });
});

describe("Security approval list", () => {
  it("searches exact catalog names and saves one selected tool", async () => {
    render(<SecuritySettingsPanel />);
    const search = await screen.findByLabelText("Search approval tools");
    fireEvent.change(search, { target: { value: "run_command" } });
    const choice = await screen.findByRole("checkbox");
    fireEvent.click(choice);
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({
      toolNames: ["devtools_run_command"], revision: 0,
    }));
    expect(await screen.findByText("1 selected")).toBeTruthy();
  });

  it("refetches current policy after a save conflict", async () => {
    mocks.update.mockRejectedValue(new Error("conflict"));
    render(<SecuritySettingsPanel />);
    const search = await screen.findByLabelText("Search approval tools");
    fireEvent.change(search, { target: { value: "run_command" } });
    fireEvent.click(await screen.findByRole("checkbox"));
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(2));
    expect((await screen.findByRole("alert")).textContent).toContain("could not be saved");
  });
});
