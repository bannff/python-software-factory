import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => mocks.callTool(...a) }));

import EmbeddingsCard from "../embeddings-card";

const ok = (data: Record<string, unknown>) => ({ structuredContent: { ok: true, data } });
const CHANGE_HINT = "Set MEMORY_BACKEND=graph and MEMORY_LOCAL_EMBED_MODEL=/path/to/model.gguf in the API environment and restart.";

beforeEach(() => mocks.callTool.mockReset());

describe("EmbeddingsCard", () => {
  it("reports a non-graph backend as not enabled", async () => {
    mocks.callTool.mockResolvedValueOnce(ok({
      backend: "InMemoryStore", is_graph_backend: false, embedder_configured: false,
      is_semantic: false, load_error: "not_graph_backend", model_path: "", dimensions: 0,
      change_hint: CHANGE_HINT,
    }));
    render(<EmbeddingsCard />);
    expect(await screen.findByText("Not enabled — using a non-graph backend")).toBeTruthy();
    expect(screen.getByText(/MEMORY_BACKEND=graph/)).toBeTruthy();
  });

  it("reports the graph backend with the keyword fallback honestly", async () => {
    mocks.callTool.mockResolvedValueOnce(ok({
      backend: "graph", is_graph_backend: true, embedder_configured: true,
      is_semantic: false, load_error: "model_file_not_found", model_path: "", dimensions: 256,
      change_hint: CHANGE_HINT,
    }));
    render(<EmbeddingsCard />);
    expect(await screen.findByText("Keyword fallback (no model loaded)")).toBeTruthy();
    expect(screen.getByText("(none configured)")).toBeTruthy();
    expect(screen.getByText(/Reason: model_file_not_found/)).toBeTruthy();
  });

  it("reports a real semantic model when one is loaded", async () => {
    mocks.callTool.mockResolvedValueOnce(ok({
      backend: "graph", is_graph_backend: true, embedder_configured: true,
      is_semantic: true, load_error: null, model_path: "/models/qwen3-embed.gguf", dimensions: 1024,
      change_hint: CHANGE_HINT,
    }));
    render(<EmbeddingsCard />);
    expect(await screen.findByText("Semantic (local model)")).toBeTruthy();
    expect(screen.getByText("/models/qwen3-embed.gguf")).toBeTruthy();
    expect(screen.getByText("1024")).toBeTruthy();
  });

  it("shows retry-safe error copy without a raw exception", async () => {
    mocks.callTool.mockRejectedValueOnce(new Error("boom"));
    render(<EmbeddingsCard />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Embedding status unavailable/i);
    expect(alert.textContent).not.toContain("boom");
  });
});
