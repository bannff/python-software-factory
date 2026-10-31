import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({
  options: null as unknown,
  connectOptions: null as null | { timeout?: number; signal?: AbortSignal },
  handler: null as null | ((request: unknown) => Promise<unknown>),
  connectedUrl: "",
  closed: 0,
  connectImpl: vi.fn(),
  timeoutError: null as null | (() => Error),
}));

vi.mock("@modelcontextprotocol/client", () => {
  class MockSdkError extends Error {
    constructor(public code: string, message: string) {
      super(message);
    }
    static isInstance(value: unknown): value is MockSdkError {
      return value instanceof MockSdkError;
    }
  }
  sdk.timeoutError = () =>
    new MockSdkError("REQUEST_TIMEOUT", "Version negotiation probe timed out after 15000ms");
  return {
    Client: class {
      constructor(_info: unknown, options: unknown) {
        sdk.options = options;
      }
      setRequestHandler(_method: string, handler: (request: unknown) => Promise<unknown>) {
        sdk.handler = handler;
      }
      async connect(transport: { url: URL }, options?: { timeout?: number; signal?: AbortSignal }) {
        sdk.connectedUrl = transport.url.toString();
        sdk.connectOptions = options ?? null;
        await sdk.connectImpl();
      }
      async close() {
        sdk.closed += 1;
      }
    },
    StreamableHTTPClientTransport: class {
      constructor(public url: URL) {}
    },
    SdkError: MockSdkError,
    UnauthorizedError: { isInstance: () => false },
    SdkHttpError: { isInstance: () => false },
    SdkErrorCode: { ClientHttpAuthentication: "CLIENT_HTTP_AUTHENTICATION", RequestTimeout: "REQUEST_TIMEOUT" },
  };
});

beforeEach(() => {
  sdk.options = null;
  sdk.connectOptions = null;
  sdk.handler = null;
  sdk.connectedUrl = "";
  sdk.closed = 0;
  sdk.connectImpl.mockReset().mockResolvedValue(undefined);
  vi.resetModules();
  vi.unstubAllEnvs();
});

afterEach(async () => {
  const { cancelAllConfirmations } = await import("@/lib/mcp-confirmation");
  cancelAllConfirmations();
  const { cancelAllQuestions } = await import("@/lib/mcp-question");
  cancelAllQuestions();
});

describe("modular MCP v2 client", () => {
  it("advertises confirmation only and enables SDK-native MRTR", async () => {
    const { getMcpClient } = await import("@/lib/mcp-client");
    await getMcpClient();

    expect(sdk.options).toEqual({
      versionNegotiation: { mode: "auto", probe: { maxRetries: 0 } },
      capabilities: { elicitation: { form: {} } },
      inputRequired: { autoFulfill: true, maxRounds: 1 },
    });
    expect(sdk.options).not.toHaveProperty("sampling");
    expect(sdk.options).not.toHaveProperty("roots");
    expect(sdk.connectedUrl).toContain("/mcp");
  });

  it("reports connecting until the real MCP handshake resolves", async () => {
    let release!: () => void;
    sdk.connectImpl.mockReturnValueOnce(new Promise<void>((resolve) => { release = resolve; }));
    const client = await import("@/lib/mcp-client");
    const status = await import("@/lib/mcp-connection-status");

    const pending = client.getMcpClient();
    expect(status.getMcpConnectionState().status).toBe("connecting");
    release();
    await pending;
    expect(status.getMcpConnectionState().status).toBe("connected");

    client.resetMcpClient();
    expect(status.getMcpConnectionState().status).toBe("idle");
  });

  it("reports a failed handshake without pretending to be connected", async () => {
    sdk.connectImpl.mockRejectedValueOnce(new Error("offline"));
    const client = await import("@/lib/mcp-client");
    const status = await import("@/lib/mcp-connection-status");

    await expect(client.getMcpClient()).rejects.toThrow("offline");
    expect(status.getMcpConnectionState().status).toBe("error");
  });

  it("hands the SDK an explicit, bounded connect budget", async () => {
    const client = await import("@/lib/mcp-client");
    await client.getMcpClient();

    expect(client.mcpConnectTimeoutMs()).toBeGreaterThan(0);
    expect(sdk.connectOptions?.timeout).toBe(client.mcpConnectTimeoutMs());
    // The wall-clock deadline, so the elapsed bound matches the budget the
    // gate names even when the SDK re-applies it to the legacy handshake.
    expect(sdk.connectOptions?.signal).toBeInstanceOf(AbortSignal);
  });

  it("honours the NEXT_PUBLIC_MCP_CONNECT_TIMEOUT_MS override", async () => {
    vi.stubEnv("NEXT_PUBLIC_MCP_CONNECT_TIMEOUT_MS", "1234");
    const client = await import("@/lib/mcp-client");
    await client.getMcpClient();

    expect(client.mcpConnectTimeoutMs()).toBe(1234);
    expect(sdk.connectOptions?.timeout).toBe(1234);
  });

  it("reports a silent handshake timeout naming the server and the budget", async () => {
    sdk.connectImpl.mockRejectedValueOnce(sdk.timeoutError!());
    const client = await import("@/lib/mcp-client");
    const status = await import("@/lib/mcp-connection-status");

    await expect(client.getMcpClient()).rejects.toMatchObject({ code: "REQUEST_TIMEOUT" });
    expect(status.getMcpConnectionState().status).toBe("error");
    expect(status.getMcpConnectionState().error).toMatch(
      /\/mcp accepted the connection but did not answer the MCP handshake within 15000 ms/,
    );
  });

  it("names the underlying transport cause when the server is unreachable", async () => {
    sdk.connectImpl.mockRejectedValueOnce(new Error("offline"));
    const client = await import("@/lib/mcp-client");
    const status = await import("@/lib/mcp-connection-status");

    await expect(client.getMcpClient()).rejects.toThrow("offline");
    expect(status.getMcpConnectionState().error).toMatch(/\/mcp is unreachable: offline/);
  });

  it("returns accepted boolean confirmation through the registered handler", async () => {
    const { getMcpClient } = await import("@/lib/mcp-client");
    const broker = await import("@/lib/mcp-confirmation");
    await getMcpClient();

    const resultPromise = sdk.handler?.({
      method: "elicitation/create",
      params: {
        mode: "form",
        message: "Approve deployment?",
        requestedSchema: {
          type: "object",
          additionalProperties: false,
          properties: { approved: { type: "boolean" } },
          required: ["approved"],
        },
      },
    });
    await Promise.resolve();
    expect(broker.getConfirmationSnapshot()?.message).toBe("Approve deployment?");
    broker.resolveConfirmation("accept");
    await expect(resultPromise).resolves.toEqual({
      action: "accept", content: { approved: true },
    });
  });

  it("returns the chosen option through the registered question handler", async () => {
    const { getMcpClient } = await import("@/lib/mcp-client");
    const broker = await import("@/lib/mcp-question");
    await getMcpClient();

    const resultPromise = sdk.handler?.({
      method: "elicitation/create",
      params: {
        mode: "form",
        message: "Which environment?",
        requestedSchema: {
          type: "object",
          additionalProperties: false,
          properties: { answer: { type: "string", enum: ["staging", "prod"] } },
          required: ["answer"],
        },
      },
    });
    await Promise.resolve();
    expect(broker.getQuestionSnapshot()?.options).toEqual(["staging", "prod"]);
    broker.answerQuestion("prod");
    await expect(resultPromise).resolves.toEqual({
      action: "accept", content: { answer: "prod" },
    });
  });

  it("cancels a question left unanswered", async () => {
    const { getMcpClient } = await import("@/lib/mcp-client");
    const broker = await import("@/lib/mcp-question");
    await getMcpClient();

    const resultPromise = sdk.handler?.({
      method: "elicitation/create",
      params: {
        mode: "form",
        message: "Which environment?",
        requestedSchema: {
          type: "object",
          additionalProperties: false,
          properties: { answer: { type: "string", enum: ["staging", "prod"] } },
          required: ["answer"],
        },
      },
    });
    await Promise.resolve();
    broker.cancelQuestion();
    await expect(resultPromise).resolves.toEqual({ action: "cancel" });
  });

  it("rejects a single-option enum as an unsupported schema", async () => {
    const { getMcpClient } = await import("@/lib/mcp-client");
    await getMcpClient();
    await expect(sdk.handler?.({
      method: "elicitation/create",
      params: {
        mode: "form", message: "Confirm",
        requestedSchema: {
          type: "object", additionalProperties: false,
          properties: { answer: { type: "string", enum: ["only"] } },
          required: ["answer"],
        },
      },
    })).resolves.toEqual({ action: "cancel" });
  });

  it("cancels unsupported schemas instead of collecting arbitrary input", async () => {
    const { getMcpClient } = await import("@/lib/mcp-client");
    await getMcpClient();
    await expect(sdk.handler?.({
      method: "elicitation/create",
      params: {
        mode: "form", message: "Enter token",
        requestedSchema: {
          type: "object", additionalProperties: false,
          properties: { token: { type: "string" } }, required: ["token"],
        },
      },
    })).resolves.toEqual({ action: "cancel" });
  });
});
