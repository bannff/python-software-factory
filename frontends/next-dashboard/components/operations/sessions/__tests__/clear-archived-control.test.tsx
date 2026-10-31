import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ClearArchivedControl } from "../clear-archived-control";

const mocks = vi.hoisted(() => ({
  countClearableSessions: vi.fn(),
  clearArchivedSessions: vi.fn(),
}));
vi.mock("../session-actions", () => ({
  countClearableSessions: (...args: unknown[]) => mocks.countClearableSessions(...args),
  clearArchivedSessions: (...args: unknown[]) => mocks.clearArchivedSessions(...args),
}));

beforeEach(() => {
  mocks.countClearableSessions.mockReset().mockResolvedValue(0);
  mocks.clearArchivedSessions.mockReset().mockResolvedValue(0);
});

describe("ClearArchivedControl", () => {
  it("renders nothing when not visible", () => {
    render(<ClearArchivedControl visible={false} onCleared={vi.fn()} />);
    expect(mocks.countClearableSessions).not.toHaveBeenCalled();
  });

  it("renders nothing when the clearable count is zero", async () => {
    render(<ClearArchivedControl visible onCleared={vi.fn()} />);
    await waitFor(() => expect(mocks.countClearableSessions).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /Delete all/ })).toBeNull();
  });

  it("shows the real count and requires a confirm click before clearing", async () => {
    mocks.countClearableSessions.mockResolvedValue(5);
    const onCleared = vi.fn();
    render(<ClearArchivedControl visible onCleared={onCleared} />);
    const button = await screen.findByRole("button", { name: "Delete all (5)" });
    fireEvent.click(button);
    expect(screen.getByText("Delete all 5 archived sessions?")).toBeTruthy();
    expect(mocks.clearArchivedSessions).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(mocks.clearArchivedSessions).toHaveBeenCalled());
    expect(onCleared).toHaveBeenCalled();
  });

  it("cancels without clearing anything", async () => {
    mocks.countClearableSessions.mockResolvedValue(2);
    render(<ClearArchivedControl visible onCleared={vi.fn()} />);
    const button = await screen.findByRole("button", { name: "Delete all (2)" });
    fireEvent.click(button);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText(/archived sessions\?/)).toBeNull();
    expect(mocks.clearArchivedSessions).not.toHaveBeenCalled();
  });

  it("shows an error and stays confirmable if the clear call fails", async () => {
    mocks.countClearableSessions.mockResolvedValue(1);
    mocks.clearArchivedSessions.mockRejectedValue(new Error("Couldn’t clear archived sessions."));
    render(<ClearArchivedControl visible onCleared={vi.fn()} />);
    const button = await screen.findByRole("button", { name: "Delete all (1)" });
    fireEvent.click(button);
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});
