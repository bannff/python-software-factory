import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import KnowledgeView from "../knowledge-view";

const wrap = (data: unknown) => ({ tool: "t", result: { ok: true, data } });
const doc1 = { id: "doc_1", source: "readme.md" };
const doc2 = { id: "doc_2", source: "notes.md" };

type Handlers = Record<string, (args: unknown) => Promise<unknown>>;
function route(handlers: Handlers) {
  mocks.callTool.mockImplementation((name: string, args: unknown) =>
    (handlers[name] ?? (() => Promise.resolve(wrap({}))))(args),
  );
}

beforeEach(() => mocks.callTool.mockReset());

describe("KnowledgeView states", () => {
  it("shows a truthful loading state then the empty state", async () => {
    route({
      kb_list_documents: async () => wrap({ documents: [], total: 0 }),
      kb_get_collection_stats: async () => wrap({ collection_id: "default", document_count: 0, total_size_bytes: 0 }),
    });
    render(<KnowledgeView />);
    expect(screen.getByText(/Loading knowledge library/i)).toBeTruthy();
    await screen.findByText(/No documents yet/i);
  });

  it("renders retry copy without a raw error and re-fetches", async () => {
    route({ kb_list_documents: async () => { throw new Error("boom"); } });
    render(<KnowledgeView />);
    const alert = await screen.findByText(/Knowledge library unavailable right now/i);
    expect(alert.parentElement?.textContent).not.toContain("boom");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(mocks.callTool.mock.calls.filter((c) => c[0] === "kb_list_documents").length).toBeGreaterThan(1),
    );
  });

  it("renders the document list and stats panel", async () => {
    route({
      kb_list_documents: async () => wrap({ documents: [doc1, doc2], total: 2 }),
      kb_get_collection_stats: async () => wrap({ collection_id: "default", document_count: 2, total_size_bytes: 2048 }),
    });
    render(<KnowledgeView />);
    expect(await screen.findByText("readme.md")).toBeTruthy();
    expect(screen.getByText("notes.md")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText("2.0 KB")).toBeTruthy();
  });

  it("switches to kb_search when a search query is entered", async () => {
    route({
      kb_list_documents: async () => wrap({ documents: [doc1], total: 1 }),
      kb_search: async () => wrap({ results: [{ document_id: "doc_2", content: "notes body", score: 0.9, source: "notes.md" }], total: 1 }),
      kb_get_collection_stats: async () => wrap({ collection_id: "default", document_count: 1, total_size_bytes: 0 }),
    });
    render(<KnowledgeView />);
    await screen.findByText("readme.md");
    fireEvent.change(screen.getByLabelText("Search knowledge library"), { target: { value: "notes" } });
    await screen.findByText("notes body");
    expect(mocks.callTool.mock.calls.some((c) => c[0] === "kb_search" && (c[1] as { query: string }).query === "notes")).toBe(true);
  });

  it("deletes a document and refreshes the list", async () => {
    let deleted = false;
    route({
      kb_list_documents: async () => wrap({ documents: deleted ? [] : [doc1], total: deleted ? 0 : 1 }),
      kb_get_collection_stats: async () => wrap({ collection_id: "default", document_count: deleted ? 0 : 1, total_size_bytes: 0 }),
      kb_delete_document: async () => { deleted = true; return wrap({ ok: true, document_id: "doc_1" }); },
    });
    render(<KnowledgeView />);
    await screen.findByText("readme.md");
    fireEvent.click(screen.getByRole("button", { name: "Delete document doc_1" }));
    await waitFor(() => expect(screen.queryByText("readme.md")).toBeNull());
  });

  it("ingests a new document through the add form", async () => {
    let ingested = false;
    route({
      kb_list_documents: async () => wrap({ documents: ingested ? [doc1] : [], total: ingested ? 1 : 0 }),
      kb_get_collection_stats: async () => wrap({ collection_id: "default", document_count: ingested ? 1 : 0, total_size_bytes: 0 }),
      kb_ingest: async (args) => {
        ingested = true;
        expect((args as { content: string }).content).toBe("Hello knowledge base");
        return wrap({ document_id: "doc_1", status: "ingested" });
      },
    });
    render(<KnowledgeView />);
    await screen.findByText(/No documents yet/i);
    fireEvent.click(screen.getByRole("button", { name: "Add a new document" }));
    fireEvent.change(screen.getByLabelText("Content"), { target: { value: "Hello knowledge base" } });
    fireEvent.click(screen.getByRole("button", { name: "Add document" }));
    await waitFor(() => expect(mocks.callTool.mock.calls.some((c) => c[0] === "kb_ingest")).toBe(true));
    await screen.findByText("readme.md");
  });
});
