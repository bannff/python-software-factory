import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const callToolMock = vi.fn();

vi.mock("@/lib/mcp-client", () => ({
  getMcpClient: async () => ({ callTool: callToolMock }),
}));

function catalogCallResult(tools: Array<{ brick: string; name: string; qualified_name: string }>) {
  return {
    structuredContent: {
      schema_version: "v1", ok: true,
      data: { tools, aliases: { ml: "machine_learning" }, count: tools.length },
      error: null, idempotency_key: null,
    },
    content: [], isError: false,
  };
}

beforeEach(() => {
  callToolMock.mockReset();
  vi.resetModules();
});

afterEach(() => vi.clearAllMocks());

describe("callTool", () => {
  it("dispatches a canonical native MCP-v2 tool through call_brick_tool", async () => {
    const callResult = (payload: unknown) => ({
      structuredContent: {
        schema_version: "v1", ok: true,
        data: { ok: true, result: { kind: "tool", structured_content: payload, content: [], meta: {} } },
        error: null, idempotency_key: null,
      },
      content: [], isError: false,
    });
    callToolMock.mockImplementation(async (params: { name: string; arguments: Record<string, unknown> }) => {
      if (params.name === "get_tool_catalog") {
        return catalogCallResult([
          { brick: "graph", name: "graph_get_stats", qualified_name: "graph_get_stats" },
        ]);
      }
      expect(params).toEqual({
        name: "call_brick_tool",
        arguments: { brick_name: "graph", tool_name: "graph_get_stats", arguments: "{}" },
      });
      return callResult({ schema_version: "v1", ok: true, data: { node_count: 3 } });
    });
    const { callTool } = await import("@/lib/api");
    const result = await callTool("graph_get_stats", {});
    expect(result).toEqual({
      tool: "graph_get_stats",
      result: { schema_version: "v1", ok: true, data: { node_count: 3 } },
    });
  });

  it("serializes inner arguments exactly once", async () => {
    callToolMock.mockImplementation(async (params: { name: string; arguments: Record<string, unknown> }) => {
      if (params.name === "get_tool_catalog") {
        return catalogCallResult([
          { brick: "cache", name: "cache_set", qualified_name: "cache_set" },
        ]);
      }
      expect(params).toEqual({
        name: "call_brick_tool",
        arguments: {
          brick_name: "cache", tool_name: "cache_set",
          arguments: JSON.stringify({ key: "k", value: "v" }),
        },
      });
      return {
        structuredContent: {
          schema_version: "v1", ok: true,
          data: { ok: true, result: { kind: "tool", structured_content: { ok: true, data: { success: true } }, content: [], meta: {} } },
        },
        content: [], isError: false,
      };
    });
    const { callTool } = await import("@/lib/api");
    await callTool("cache_set", { key: "k", value: "v" });
  });

  it("fails before invocation when no canonical catalog target exists", async () => {
    callToolMock.mockImplementation(async (params: { name: string }) => {
      if (params.name === "get_tool_catalog") return catalogCallResult([]);
      throw new Error("unexpected native invocation");
    });
    const { callTool, ApiError } = await import("@/lib/api");
    await expect(callTool("no_such_tool", {})).rejects.toBeInstanceOf(ApiError);
  });

  it("maps a legacy alias to the server-published canonical name", async () => {
    callToolMock.mockImplementation(async (params: { name: string; arguments?: Record<string, unknown> }) => {
      if (params.name === "get_tool_catalog") {
        return catalogCallResult([{
          brick: "machine_learning", name: "ml_get_views",
          qualified_name: "machine_learning_ml_get_views",
        }]);
      }
      expect(params.name).toBe("call_brick_tool");
      expect(params.arguments).toEqual({
        brick_name: "machine_learning", tool_name: "ml_get_views", arguments: "{}",
      });
      return {
        structuredContent: {
          schema_version: "v1", ok: true,
          data: { ok: true, result: { kind: "tool", structured_content: { ok: true, data: [] }, content: [], meta: {} } },
        },
        content: [], isError: false,
      };
    });
    const { callTool } = await import("@/lib/api");
    await callTool("ml_get_views", {});
  });
});

describe("listTools", () => {
  it("returns canonical public names from the generated catalog", async () => {
    callToolMock.mockImplementation(async () => catalogCallResult([
      { brick: "graph", name: "graph_get_stats", qualified_name: "graph_get_stats" },
      { brick: "workflow", name: "workflow_get_views", qualified_name: "workflow_get_views" },
    ]));
    const { listTools } = await import("@/lib/api");
    expect(await listTools()).toEqual({
      tools: ["graph_get_stats", "workflow_get_views"], count: 2,
    });
  });
});

describe("call_brick_tool envelope regression", () => {
  const singleToolCatalog = () =>
    catalogCallResult([
      { brick: "graph", name: "graph_get_stats", qualified_name: "graph_get_stats" },
    ]);

  it("unwraps a structuredContent ok:true envelope with a structured_content payload", async () => {
    const payload = { node_count: 7 };
    callToolMock.mockImplementation(async (params: { name: string }) => {
      if (params.name === "get_tool_catalog") return singleToolCatalog();
      return {
        structuredContent: {
          schema_version: "v1", ok: true,
          data: { ok: true, result: { kind: "tool", structured_content: payload, content: [], meta: {} } },
          error: null, idempotency_key: null,
        },
        content: [], isError: false,
      };
    });
    const { callTool } = await import("@/lib/api");
    await expect(callTool("graph_get_stats", {})).resolves.toEqual({
      tool: "graph_get_stats",
      result: payload,
    });
  });

  it("parses a single text-content JSON envelope", async () => {
    const payload = { node_count: 9 };
    const outerEnvelope = {
      schema_version: "v1", ok: true,
      data: { ok: true, result: { kind: "tool", structured_content: payload, content: [], meta: {} } },
      error: null, idempotency_key: null,
    };
    callToolMock.mockImplementation(async (params: { name: string }) => {
      if (params.name === "get_tool_catalog") return singleToolCatalog();
      return {
        content: [{ type: "text", text: JSON.stringify(outerEnvelope) }],
        isError: false,
      };
    });
    const { callTool } = await import("@/lib/api");
    await expect(callTool("graph_get_stats", {})).resolves.toEqual({
      tool: "graph_get_stats",
      result: payload,
    });
  });

  it("maps an outer ok:false envelope to ApiError 502", async () => {
    callToolMock.mockImplementation(async (params: { name: string }) => {
      if (params.name === "get_tool_catalog") return singleToolCatalog();
      return {
        structuredContent: {
          schema_version: "v1", ok: false,
          data: null,
          error: { code: "BRICK_TOOL_FAILED", message: "boom" },
          idempotency_key: null,
        },
        content: [], isError: false,
      };
    });
    const { callTool, ApiError } = await import("@/lib/api");
    const failure = await callTool("graph_get_stats", {}).catch((err: unknown) => err);
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as InstanceType<typeof ApiError>).status).toBe(502);
  });

  it("maps an inner transport ok:false envelope to ApiError 502", async () => {
    callToolMock.mockImplementation(async (params: { name: string }) => {
      if (params.name === "get_tool_catalog") return singleToolCatalog();
      return {
        structuredContent: {
          schema_version: "v1", ok: true,
          data: { ok: false, error: { code: "TOOL_FAILED", message: "tool boom" } },
          error: null, idempotency_key: null,
        },
        content: [], isError: false,
      };
    });
    const { callTool, ApiError } = await import("@/lib/api");
    const failure = await callTool("graph_get_stats", {}).catch((err: unknown) => err);
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as InstanceType<typeof ApiError>).status).toBe(502);
  });

  it("maps an unrecognizable envelope to ApiError 502", async () => {
    callToolMock.mockImplementation(async (params: { name: string }) => {
      if (params.name === "get_tool_catalog") return singleToolCatalog();
      return {
        structuredContent: { unexpected: "shape" },
        content: [], isError: false,
      };
    });
    const { callTool, ApiError } = await import("@/lib/api");
    const failure = await callTool("graph_get_stats", {}).catch((err: unknown) => err);
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as InstanceType<typeof ApiError>).status).toBe(502);
  });
});
