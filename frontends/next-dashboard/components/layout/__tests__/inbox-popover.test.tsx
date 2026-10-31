import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

// jsdom lacks the observers/pointer APIs Radix Popover positioning relies on.
class ResizeObserverStub { observe() {} unobserve() {} disconnect() {} }
(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub;
Element.prototype.hasPointerCapture = () => false;
Element.prototype.setPointerCapture = () => {};
Element.prototype.releasePointerCapture = () => {};
Element.prototype.scrollIntoView = () => {};

const mocks = vi.hoisted(() => ({ callTool: vi.fn(), push: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { InboxPopover } from "@/components/layout/inbox-popover";

const RECORDS = [
  {
    notification_id: "ntf_art", kind: "schedule_fired", title: "Schedule fired",
    body: "Nightly scan started", priority: "critical",
    target: { kind: "artifact", slug: "scan-report" },
    created_at: "2026-09-13T18:00:00Z", read_at: null, revision: 4,
  },
  {
    notification_id: "ntf_crew", kind: "crew_ready", title: "Crew ready", body: "",
    priority: "default", target: { kind: "crew", crew_id: "redteam-crew" },
    created_at: "2026-09-13T17:00:00Z", read_at: "2026-09-13T17:05:00Z", revision: 1,
  },
  {
    notification_id: "ntf_sess", kind: "session_update", title: "Session updated",
    body: "A session moved on", priority: "passive",
    target: { kind: "session", session_id: "sess-1" },
    created_at: "2026-09-13T16:00:00Z", read_at: null, revision: 2,
  },
];

function listResult(records = RECORDS) {
  return { tool: "notification_inbox_list", result: { notifications: records, count: records.length } };
}

function routeList(overrides: Record<string, unknown> = {}) {
  mocks.callTool.mockImplementation((name: string) => {
    if (name === "notification_inbox_list") return Promise.resolve(overrides.list ?? listResult());
    if (name in overrides) return (overrides[name] as () => Promise<unknown>)();
    return Promise.resolve({});
  });
}

const listCalls = () => mocks.callTool.mock.calls.filter((c) => c[0] === "notification_inbox_list").length;

beforeEach(() => {
  mocks.callTool.mockReset();
  mocks.push.mockReset();
});

describe("InboxPopover", () => {
  it("shows the unread count on the bell and in a polite live region", async () => {
    routeList();
    render(<InboxPopover />);
    expect(await screen.findByRole("button", { name: "Notifications, 2 unread" })).toBeTruthy();
    expect(screen.getByText("2 unread notifications")).toBeTruthy();
  });

  it("lists notifications with plain title/body and no raw IDs or reason codes", async () => {
    routeList();
    render(<InboxPopover />);
    await screen.findByRole("button", { name: /Notifications/ });
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    expect(await screen.findByText("Schedule fired")).toBeTruthy();
    expect(screen.getByText("Nightly scan started")).toBeTruthy();
    expect(screen.queryByText(/ntf_art/)).toBeNull();
    expect(screen.queryByText(/schedule_fired/)).toBeNull();
  });

  it("marks one read with the record revision and no identity args", async () => {
    routeList();
    render(<InboxPopover />);
    await screen.findByRole("button", { name: /Notifications/ });
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    const row = (await screen.findByText("Schedule fired")).closest("li") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Mark read" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith(
      "notification_inbox_mark_read", { notification_id: "ntf_art", expected_revision: 4 },
    ));
    const listArgs = mocks.callTool.mock.calls.find((c) => c[0] === "notification_inbox_list")?.[1];
    expect(listArgs).toEqual({ limit: 50, offset: 0 });
  });

  it("marks all read fenced by the expected unread count", async () => {
    routeList();
    render(<InboxPopover />);
    await screen.findByRole("button", { name: /Notifications/ });
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Mark all read" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith(
      "notification_inbox_mark_all_read", { expected_unread_count: 2 },
    ));
  });

  it("refreshes rather than lying on a mark-all count conflict", async () => {
    routeList({ notification_inbox_mark_all_read: () => Promise.reject(new Error("conflict")) });
    render(<InboxPopover />);
    await screen.findByRole("button", { name: /Notifications/ });
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    const before = listCalls();
    fireEvent.click(await screen.findByRole("button", { name: "Mark all read" }));
    await waitFor(() => expect(listCalls()).toBeGreaterThan(before));
  });

  it("reauthorizes and opens an exact session target", async () => {
    routeList();
    render(<InboxPopover />);
    await screen.findByRole("button", { name: /Notifications/ });
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    const row = (await screen.findByText("Session updated")).closest("li") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Open" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith(
      "notification_inbox_resolve_target", { notification_id: "ntf_sess" },
    ));
    expect(mocks.push).toHaveBeenCalledWith("/sessions/sess-1");
  });

  it("renders an empty state when there are no notifications", async () => {
    routeList({ list: listResult([]) });
    render(<InboxPopover />);
    fireEvent.click(await screen.findByRole("button", { name: "Notifications" }));
    expect(await screen.findByText(/all caught up/i)).toBeTruthy();
  });

  it("renders a truthful error with retry", async () => {
    mocks.callTool.mockImplementation((name: string) =>
      name === "notification_inbox_list"
        ? Promise.reject(new Error("down"))
        : Promise.resolve({}));
    render(<InboxPopover />);
    fireEvent.click(await screen.findByRole("button", { name: "Notifications" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(/Notifications unavailable/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
  });
});
