import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));
vi.mock("@copilotkit/react-core/v2", () => ({ useAgent: () => ({ agent: { threadId: "thread" } }) }));

import LessonsView from "../lessons-view";

const ID = "les_" + "a".repeat(32);
const ID2 = "les_" + "b".repeat(32);
const wrap = (data: unknown) => ({ tool: "t", result: { ok: true, data } });
const proposed = {
  lesson_id: ID, rule: "Prefer dark mode", negative: "Avoid light backgrounds",
  category: "preference", scope: "global", scope_id: null, source: "feedback",
  evidence: ["Chat on 9/12"], status: "proposed", revision: 2,
  updated_at: "2026-09-13T00:00:00Z",
};
const accepted = {
  ...proposed, lesson_id: ID2, rule: "Always run tests", status: "accepted",
  source: "user_explicit", negative: null, revision: 1,
};

type Handlers = Record<string, (args: unknown) => Promise<unknown>>;
function route(handlers: Handlers) {
  mocks.callTool.mockImplementation((name: string, args: unknown) =>
    (handlers[name] ?? (() => Promise.resolve(wrap({}))))(args),
  );
}

beforeEach(() => mocks.callTool.mockReset());

describe("LessonsView states", () => {
  it("shows a truthful loading state", async () => {
    route({ lessons_list: async () => wrap({ lessons: [] }) });
    render(<LessonsView />);
    expect(screen.getByText(/Loading lessons/i)).toBeTruthy();
    await screen.findByText(/No lessons yet/i);
  });

  it("explains the empty state in plain language", async () => {
    route({ lessons_list: async () => wrap({ lessons: [] }) });
    render(<LessonsView />);
    expect(await screen.findByText(/No lessons yet/i)).toBeTruthy();
  });

  it("renders retry copy without a raw code and re-fetches", async () => {
    route({ lessons_list: async () => { throw new Error("boom"); } });
    render(<LessonsView />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Lessons unavailable right now/i);
    expect(alert.textContent).not.toContain("boom");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(mocks.callTool.mock.calls.filter((c) => c[0] === "lessons_list").length).toBeGreaterThan(1),
    );
  });

  it("shows plain language, never raw enum codes", async () => {
    route({ lessons_list: async () => wrap({ lessons: [proposed, accepted] }) });
    render(<LessonsView />);
    expect(await screen.findByText("Prefer dark mode")).toBeTruthy();
    expect(screen.getByText("Suggested")).toBeTruthy();
    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.queryByText("proposed")).toBeNull();
    expect(screen.queryByText("user_explicit")).toBeNull();
    expect(screen.queryByText(ID)).toBeNull();
  });
});

describe("LessonsView focus + a11y", () => {
  it("deep-links a lesson, focuses the detail heading, and reports it once", async () => {
    route({ lessons_list: async () => wrap({ lessons: [proposed] }) });
    const onFocusHandled = vi.fn();
    render(<LessonsView focusLessonId={ID} onFocusHandled={onFocusHandled} />);
    await waitFor(() => expect(onFocusHandled).toHaveBeenCalledTimes(1));
    const heading = screen.getByRole("heading", { name: "Prefer dark mode" });
    expect(document.activeElement).toBe(heading);
    expect(screen.getByRole("list", { name: "Lessons" })).toBeTruthy();
  });
});

describe("LessonsView curation", () => {
  async function open() {
    render(<LessonsView />);
    fireEvent.click(await screen.findByRole("button", { name: /Prefer dark mode/ }));
  }

  it("accepts with the exact revision-fenced MCP args", async () => {
    route({
      lessons_list: async () => wrap({ lessons: [proposed] }),
      lessons_accept: async () => wrap({ lesson: { ...proposed, status: "accepted", revision: 3 } }),
    });
    await open();
    fireEvent.click(screen.getByRole("button", { name: /Keep lesson/ }));
    await waitFor(() =>
      expect(mocks.callTool).toHaveBeenCalledWith("lessons_accept", { lesson_id: ID, expected_revision: 2, envelope: { session_id: "thread" } }),
    );
  });

  it("surfaces a plain conflict-refresh notice when curation loses a race", async () => {
    route({
      lessons_list: async () => wrap({ lessons: [proposed] }),
      lessons_accept: async () => { throw new Error("conflict"); },
      lessons_get: async () => wrap({ lesson: { ...proposed, revision: 3 } }),
    });
    await open();
    fireEvent.click(screen.getByRole("button", { name: /Keep lesson/ }));
    const alert = await screen.findByText(/changed since you opened it/i);
    expect(alert).toBeTruthy();
    expect(alert.textContent).not.toContain("conflict");
  });

  it("shows a truthful deleted state after a successful delete", async () => {
    let removed = false;
    route({
      lessons_list: async () => wrap({ lessons: removed ? [] : [proposed] }),
      lessons_remove: async () => { removed = true; return wrap({ lesson_id: ID, removed: true }); },
    });
    await open();
    fireEvent.click(screen.getByRole("button", { name: /Delete/ }));
    await waitFor(() =>
      expect(mocks.callTool).toHaveBeenCalledWith("lessons_remove", { lesson_id: ID, expected_revision: 2, envelope: { session_id: "thread" } }),
    );
    expect(await screen.findByText(/no longer here/i)).toBeTruthy();
  });
});
