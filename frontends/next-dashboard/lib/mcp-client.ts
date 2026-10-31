import {
  Client,
  SdkError,
  SdkErrorCode,
  SdkHttpError,
  StreamableHTTPClientTransport,
  UnauthorizedError,
  type ElicitRequest,
  type ElicitResult,
} from "@modelcontextprotocol/client";

import {
  cancelAllConfirmations,
  requestConfirmation,
} from "./mcp-confirmation";
import { setMcpConnectionStatus } from "./mcp-connection-status";
import { cancelAllQuestions, requestQuestion } from "./mcp-question";

/**
 * Singleton browser-side MCP v2 client. SDK-first pin:
 * @modelcontextprotocol/client@2.0.0 — the browser talks to the same-origin
 * local BFF and never owns the backend bearer (the BFF adds it after
 * loopback/origin admission). CopilotKit/AG-UI and mcp-ui stay independent.
 */

let clientPromise: Promise<Client> | null = null;
let clientInstance: Client | null = null;

/**
 * Connect budget in ms, applied twice: the SDK's per-request handshake budget
 * and a wall-clock deadline for the whole connect. The SDK re-applies the
 * per-request budget to the era probe and to the legacy `initialize`, so a
 * server that answers the probe late and then stalls would otherwise take
 * twice this long. Override with `NEXT_PUBLIC_MCP_CONNECT_TIMEOUT_MS`.
 */
export function mcpConnectTimeoutMs(): number {
  const raw = Number(process.env.NEXT_PUBLIC_MCP_CONNECT_TIMEOUT_MS);
  return Number.isFinite(raw) && raw > 0 ? raw : 15_000;
}

export class McpAuthenticationError extends Error {
  constructor(server: string) {
    super(`Local MCP authentication failed for ${server}. Restart Companion X with a configured local token.`);
    this.name = "McpAuthenticationError";
  }
}

export function normalizeMcpConnectionError(error: unknown): unknown {
  if (UnauthorizedError.isInstance(error)
      || (SdkHttpError.isInstance(error)
          && error.code === SdkErrorCode.ClientHttpAuthentication)) {
    return new McpAuthenticationError(mcpUrl().toString());
  }
  return error;
}

/**
 * Turn a failed handshake into a message naming the server and the underlying
 * cause (auth vs timeout vs transport), so the connection gate can show why
 * tools are unavailable instead of a generic string.
 */
export function describeMcpConnectionError(
  error: unknown,
  server: string,
  timeoutMs: number,
): string {
  if (error instanceof McpAuthenticationError) return error.message;
  if (SdkError.isInstance(error) && error.code === SdkErrorCode.RequestTimeout) {
    return `${server} accepted the connection but did not answer the MCP handshake within ${timeoutMs} ms.`;
  }
  const cause = error instanceof Error ? error.message : String(error);
  return `${server} is unreachable: ${cause}`;
}

function mcpUrl(): URL {
  if (typeof window === "undefined") {
    const base = process.env.API_URL || "http://localhost:8000";
    return new URL(`${base}/mcp/`);
  }
  return new URL("/mcp", window.location.origin);
}

function isBooleanConfirmation(schema: unknown): string | null {
  if (!schema || typeof schema !== "object") return null;
  const value = schema as {
    type?: unknown;
    properties?: Record<string, { type?: unknown; anyOf?: Array<{ type?: unknown }> }>;
    required?: unknown;
    additionalProperties?: unknown;
  };
  if (value.type !== "object" || value.additionalProperties !== false) return null;
  const entries = Object.entries(value.properties ?? {});
  if (entries.length !== 1) return null;
  const [field, fieldSchema] = entries[0];
  const types = fieldSchema.anyOf?.map((item) => item.type) ?? [fieldSchema.type];
  const nonNull = types.filter((type) => type !== "null");
  const required = Array.isArray(value.required) && value.required.includes(field);
  return required && nonNull.length === 1 && nonNull[0] === "boolean" ? field : null;
}

interface EnumChoice {
  field: string;
  options: string[];
}

/** Detect a single required string field with a fixed `enum` — a multiple-choice question. */
function isEnumChoice(schema: unknown): EnumChoice | null {
  if (!schema || typeof schema !== "object") return null;
  const value = schema as {
    type?: unknown;
    properties?: Record<string, { type?: unknown; enum?: unknown }>;
    required?: unknown;
    additionalProperties?: unknown;
  };
  if (value.type !== "object" || value.additionalProperties !== false) return null;
  const entries = Object.entries(value.properties ?? {});
  if (entries.length !== 1) return null;
  const [field, fieldSchema] = entries[0];
  const required = Array.isArray(value.required) && value.required.includes(field);
  if (!required || fieldSchema.type !== "string" || !Array.isArray(fieldSchema.enum)) return null;
  const options = fieldSchema.enum.filter((item): item is string => typeof item === "string");
  return options.length >= 2 ? { field, options } : null;
}

async function handleElicitation(request: ElicitRequest): Promise<ElicitResult> {
  if (typeof window === "undefined") return { action: "cancel" };
  const params = request.params;
  if (params.mode !== undefined && params.mode !== "form") return { action: "cancel" };
  const choice = isEnumChoice(params.requestedSchema);
  if (choice) {
    const decision = await requestQuestion(params.message, choice.field, choice.options);
    return decision.action === "answer"
      ? { action: "accept", content: { [choice.field]: decision.value } }
      : { action: "cancel" };
  }
  const field = isBooleanConfirmation(params.requestedSchema);
  if (!field) return { action: "cancel" };
  const decision = await requestConfirmation(params.message, field);
  return decision === "accept"
    ? { action: "accept", content: { [field]: true } }
    : { action: decision };
}

async function connect(): Promise<Client> {
  const client = new Client(
    { name: "companion-x-next-dashboard", version: "1.0.0" },
    {
      versionNegotiation: { mode: "auto", probe: { maxRetries: 0 } },
      capabilities: { elicitation: { form: {} } },
      inputRequired: { autoFulfill: true, maxRounds: 1 },
    },
  );
  client.setRequestHandler("elicitation/create", handleElicitation);
  const timeout = mcpConnectTimeoutMs();
  await client.connect(new StreamableHTTPClientTransport(mcpUrl(), {
    requestInit: { headers: { "x-companion-x-local": "1" } },
  }), { timeout, signal: AbortSignal.timeout(timeout) });
  clientInstance = client;
  return client;
}

/** Get the shared MCP client, connecting on first use. */
export async function getMcpClient(): Promise<Client> {
  if (!clientPromise) {
    setMcpConnectionStatus("connecting");
    clientPromise = connect().then((client) => {
      setMcpConnectionStatus("connected");
      return client;
    }).catch((error) => {
      clientPromise = null;
      clientInstance = null;
      cancelAllConfirmations();
      cancelAllQuestions();
      const normalized = normalizeMcpConnectionError(error);
      setMcpConnectionStatus(
        "error",
        describeMcpConnectionError(normalized, mcpUrl().toString(), mcpConnectTimeoutMs()),
      );
      throw normalized;
    });
  }
  return clientPromise;
}

/** Reset the singleton and cancel pending confirmation and question prompts. */
export function resetMcpClient(): void {
  cancelAllConfirmations();
  cancelAllQuestions();
  void clientInstance?.close();
  clientInstance = null;
  clientPromise = null;
  setMcpConnectionStatus("idle");
}

export function retryMcpConnection(): Promise<Client> {
  resetMcpClient();
  return getMcpClient();
}
