import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import MemoryView from "../memory-view";

const wrap = (data: unknown) => ({ tool: "t", result: { ok: true, data } });
const fact = {
  id: "mem_1", user_id: "u", content: "Prefers dark mode", memory_type: "long_term",
  category: "preference", metadata: {}, relevance_score: 1,
  created_at: "2026-09-13T00:00:00Z", updated_at: null, expires_at: null,
};
const episode = {
  id: "mem_2", user_id: "u", content: "Ran the deploy at noon", memory_type: "episodic",
  category: "event", metadata: {}, relevance_score: 0.9,
  created_at: "2026-09-14T00:00:00Z", updated_at: null, expires_at: null,
};

type Handlers = Record<string, (args: unknown) => Promise<unknown>>;
const DEFAULT_EMBEDDING_STATUS = wrap({
  backend: "InMemoryStore", is_graph_backend: false, embedder_configured: false,
  is_semantic: false, load_error: "not_graph_backend", model_path: "", dimensions: 0,
  change_hint: "Set MEMORY_BACKEND=graph and MEMORY_LOCAL_EMBED_MODEL=... and restart.",
});
function route(handlers: Handlers) {
  mocks.callTool.mockImplementation((name: string, args: unknown) =>
    (handlers[name] ?? (name === "memory_get_embedding_status"
      ? () => Promise.resolve(DEFAULT_EMBEDDING_STATUS)
      : () => Promise.resolve(wrap({}))))(args),
  );
}

beforeEach(() => mocks.callTool.mockReset());

describe("MemoryView states", () => {
  it("shows a truthful loading state then the empty state", async () => {
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [], count: 0 }),
      memory_stats: async () => wrap({ total_memories: 0, by_type: {}, by_category: {} }),
    });
    render(<MemoryView />);
    expect(screen.getByText(/Loading memory/i)).toBeTruthy();
    await screen.findByText(/No memories yet/i);
  });

  it("renders retry copy without a raw code and re-fetches", async () => {
    route({ memory_list: async () => { throw new Error("boom"); } });
    render(<MemoryView />);
    const alert = await screen.findByText(/Memory unavailable right now/i);
    expect(alert.textContent).toMatch(/Memory unavailable right now/i);
    expect(alert.parentElement?.textContent).not.toContain("boom");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(mocks.callTool.mock.calls.filter((c) => c[0] === "memory_list").length).toBeGreaterThan(1),
    );
  });

  it("renders the list and stats panel", async () => {
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [fact, episode], count: 2 }),
      memory_stats: async () => wrap({
        total_memories: 2, by_type: { long_term: 1, episodic: 1 }, by_category: {},
      }),
    });
    render(<MemoryView />);
    expect(await screen.findByText("Prefers dark mode")).toBeTruthy();
    expect(screen.getByText("Ran the deploy at noon")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
  });

  it("opens the recall inspection panel and shows the real graph neighborhood", async () => {
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [fact], count: 1 }),
      memory_stats: async () => wrap({ total_memories: 1, by_type: {}, by_category: {} }),
      memory_recall_inspect: async () => wrap({
        memory_id: "mem_1", supported: true, owner_id: "u", followed: episode,
        similar: [{ memory: episode, score: 0.91 }],
      }),
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    fireEvent.click(screen.getByLabelText("Inspect recall for memory mem_1"));
    await screen.findByText("Why this surfaced");
    expect(screen.getByText(/0\.91/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Close recall inspection"));
    expect(screen.queryByText("Why this surfaced")).toBeNull();
  });

  it("opens the history panel and shows the replaced-experiences chain", async () => {
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [fact], count: 1 }),
      memory_stats: async () => wrap({ total_memories: 1, by_type: {}, by_category: {} }),
      memory_history: async () => wrap({
        memory_id: "mem_1", supported: true,
        versions: [episode, fact],
      }),
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    fireEvent.click(screen.getByLabelText("View history for memory mem_1"));
    await screen.findByText("Replaced experiences");
    expect(screen.getByText("Ran the deploy at noon")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /restore/i })).toBeNull();
    fireEvent.click(screen.getByLabelText("Close memory history"));
    expect(screen.queryByText("Replaced experiences")).toBeNull();
  });

  it("shows an unsupported message when the active adapter has no graph substrate", async () => {
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [fact], count: 1 }),
      memory_stats: async () => wrap({ total_memories: 1, by_type: {}, by_category: {} }),
      memory_recall_inspect: async () => wrap({ memory_id: "mem_1", supported: false }),
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    fireEvent.click(screen.getByLabelText("Inspect recall for memory mem_1"));
    await screen.findByText(/no graph to inspect/i);
  });

  it("switches to memory_retrieve when a search query is entered", async () => {
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [fact], count: 1 }),
      memory_retrieve: async () => wrap({ memories: [episode], count: 1 }),
      memory_stats: async () => wrap({ total_memories: 1, by_type: {}, by_category: {} }),
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    fireEvent.change(screen.getByLabelText("Search memory"), { target: { value: "deploy" } });
    await screen.findByText("Ran the deploy at noon");
    expect(mocks.callTool.mock.calls.some((c) => c[0] === "memory_retrieve" && (c[1] as { query: string }).query === "deploy")).toBe(true);
  });

  it("deletes a memory and refreshes the list", async () => {
    let deleted = false;
    route({
      memory_list: async () => wrap({
        user_id: "u", memories: deleted ? [] : [fact], count: deleted ? 0 : 1,
      }),
      memory_stats: async () => wrap({ total_memories: deleted ? 0 : 1, by_type: {}, by_category: {} }),
      memory_delete: async () => { deleted = true; return wrap({ memory_id: "mem_1", deleted: true }); },
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    fireEvent.click(screen.getByRole("button", { name: "Delete memory mem_1" }));
    await waitFor(() => expect(screen.queryByText("Prefers dark mode")).toBeNull());
  });

  it("corrects a memory's content and refreshes the list", async () => {
    let content = "Prefers dark mode";
    route({
      memory_list: async () => wrap({
        user_id: "u", memories: [{ ...fact, content }], count: 1,
      }),
      memory_stats: async () => wrap({ total_memories: 1, by_type: {}, by_category: {} }),
      memory_update: async (args: unknown) => {
        content = (args as { content: string }).content;
        return wrap({ memory_id: "mem_1", updated: true, memory: { ...fact, content } });
      },
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    fireEvent.click(screen.getByRole("button", { name: "Edit memory mem_1" }));
    const textarea = screen.getByRole("textbox", { name: "Edit memory mem_1" });
    fireEvent.change(textarea, { target: { value: "Prefers light mode" } });
    fireEvent.click(screen.getByRole("button", { name: "Save correction for memory mem_1" }));
    await waitFor(() => expect(screen.queryByText("Prefers light mode")).toBeTruthy());
    expect(mocks.callTool.mock.calls.some(
      (c) => c[0] === "memory_update" && (c[1] as { content: string }).content === "Prefers light mode",
    )).toBe(true);
  });

  it("shows a truthful error and keeps editing open when the correction fails", async () => {
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [fact], count: 1 }),
      memory_stats: async () => wrap({ total_memories: 1, by_type: {}, by_category: {} }),
      memory_update: async () => wrap({ memory_id: "mem_1", updated: false, error: "memory not found" }),
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    fireEvent.click(screen.getByRole("button", { name: "Edit memory mem_1" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Edit memory mem_1" }), { target: { value: "new content" } });
    fireEvent.click(screen.getByRole("button", { name: "Save correction for memory mem_1" }));
    await screen.findByText("memory not found");
    expect(screen.getByRole("textbox", { name: "Edit memory mem_1" })).toBeTruthy();
  });

  it("cancels editing without saving", async () => {
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [fact], count: 1 }),
      memory_stats: async () => wrap({ total_memories: 1, by_type: {}, by_category: {} }),
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    fireEvent.click(screen.getByRole("button", { name: "Edit memory mem_1" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Edit memory mem_1" }), { target: { value: "discarded draft" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancel editing memory mem_1" }));
    expect(screen.queryByRole("textbox", { name: "Edit memory mem_1" })).toBeNull();
    expect(screen.getByText("Prefers dark mode")).toBeTruthy();
    expect(mocks.callTool.mock.calls.some((c) => c[0] === "memory_update")).toBe(false);
  });

  it("previews then confirms a bulk delete, deleting only what the preview showed", async () => {
    let deleted = false;
    route({
      memory_list: async () => wrap({
        user_id: "u", memories: deleted ? [] : [fact, episode], count: deleted ? 0 : 2,
      }),
      memory_stats: async () => wrap({ total_memories: deleted ? 0 : 2, by_type: {}, by_category: {} }),
      memory_bulk_preview: async () => wrap({ user_id: "u", matched_count: 2, sample: [fact, episode] }),
      memory_bulk_delete: async () => { deleted = true; return wrap({ user_id: "u", deleted_count: 2, deleted_ids: ["mem_1", "mem_2"] }); },
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    fireEvent.click(screen.getByRole("button", { name: "Delete matching…" }));
    await screen.findByText(/will delete/i);
    const dialog = screen.getByRole("alertdialog", { name: "Confirm bulk delete" });
    expect(dialog.textContent).toMatch(/\b2\b/);
    fireEvent.click(screen.getByRole("button", { name: "Delete 2" }));
    await waitFor(() => expect(screen.queryByText("Prefers dark mode")).toBeNull());
    expect(screen.getByText(/deleted 2 matching memories/i)).toBeTruthy();
  });

  it("cancels a bulk delete without calling memory_bulk_delete", async () => {
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [fact], count: 1 }),
      memory_stats: async () => wrap({ total_memories: 1, by_type: {}, by_category: {} }),
      memory_bulk_preview: async () => wrap({ user_id: "u", matched_count: 1, sample: [fact] }),
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    fireEvent.click(screen.getByRole("button", { name: "Delete matching…" }));
    await screen.findByText(/will delete/i);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText(/will delete/i)).toBeNull();
    expect(screen.getByText("Prefers dark mode")).toBeTruthy();
    expect(mocks.callTool.mock.calls.some((c) => c[0] === "memory_bulk_delete")).toBe(false);
  });

  it("shows a truthful error when the bulk preview itself fails", async () => {
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [fact], count: 1 }),
      memory_stats: async () => wrap({ total_memories: 1, by_type: {}, by_category: {} }),
      memory_bulk_preview: async () => wrap({ user_id: null, matched_count: 0, sample: [], error: "user_id required" }),
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    fireEvent.click(screen.getByRole("button", { name: "Delete matching…" }));
    await screen.findByText("user_id required");
    expect(screen.queryByText(/will delete/i)).toBeNull();
  });

  it("shows scope/agent badges when present in metadata", async () => {
    const scoped = {
      ...fact, id: "mem_3", metadata: { scope: "shared", agent: "dev" },
    };
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [scoped], count: 1 }),
      memory_stats: async () => wrap({ total_memories: 1, by_type: {}, by_category: {} }),
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    expect(screen.getByText("shared")).toBeTruthy();
    expect(screen.getByText("· dev")).toBeTruthy();
  });

  it("sends the scope=shared metadata filter to memory_list when 'Shared only' is selected", async () => {
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [fact], count: 1 }),
      memory_stats: async () => wrap({ total_memories: 1, by_type: {}, by_category: {} }),
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    fireEvent.change(screen.getByLabelText("Filter by memory scope"), { target: { value: "shared" } });
    await waitFor(() =>
      expect(mocks.callTool.mock.calls.some(
        (c) => c[0] === "memory_list" && (c[1] as { metadata?: Record<string, string> }).metadata?.scope === "shared",
      )).toBe(true),
    );
  });

  it("sends no metadata filter to memory_list for the default 'Own + shared' scope", async () => {
    route({
      memory_list: async () => wrap({ user_id: "u", memories: [fact], count: 1 }),
      memory_stats: async () => wrap({ total_memories: 1, by_type: {}, by_category: {} }),
    });
    render(<MemoryView />);
    await screen.findByText("Prefers dark mode");
    const initialCall = mocks.callTool.mock.calls.find((c) => c[0] === "memory_list");
    expect((initialCall?.[1] as { metadata?: unknown }).metadata).toBeUndefined();
  });
});
