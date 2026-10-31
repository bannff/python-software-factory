import { getMcpClient } from "@/lib/mcp-client";

export interface ConnectionBrick {
  name: string;
  namespace: string;
  toolsCount: number;
  loaded: boolean;
  healthy: boolean;
  error: string | null;
}

export interface ConnectionTool {
  name: string;
  description: string;
  category: string | null;
}

function dataFrom(raw: unknown): Record<string, unknown> {
  if (!raw || typeof raw !== "object") throw new Error("MCP returned an invalid response.");
  const result = raw as { structuredContent?: unknown };
  const envelope = result.structuredContent;
  if (!envelope || typeof envelope !== "object") throw new Error("MCP returned no structured data.");
  const typed = envelope as { ok?: boolean; data?: unknown; error?: unknown };
  if (typed.ok !== true || !typed.data || typeof typed.data !== "object") {
    throw new Error(typeof typed.error === "string" ? typed.error : "MCP operation failed.");
  }
  return typed.data as Record<string, unknown>;
}

function brickFrom(raw: unknown): ConnectionBrick | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  if (typeof value.name !== "string" || typeof value.namespace !== "string") return null;
  return {
    name: value.name,
    namespace: value.namespace,
    toolsCount: typeof value.tools_count === "number" ? value.tools_count : -1,
    loaded: value.loaded === true,
    healthy: value.healthy !== false,
    error: typeof value.error === "string" ? value.error : null,
  };
}

export async function listConnectionBricks(): Promise<ConnectionBrick[]> {
  const client = await getMcpClient();
  const data = dataFrom(await client.callTool({ name: "list_bricks", arguments: {} }));
  if (!Array.isArray(data.bricks)) throw new Error("MCP returned no brick inventory.");
  return data.bricks.map(brickFrom).filter((row): row is ConnectionBrick => row !== null);
}

export async function enableConnectionBrick(brickName: string): Promise<ConnectionTool[]> {
  const client = await getMcpClient();
  const data = dataFrom(await client.callTool({
    name: "get_brick_tools", arguments: { brick_name: brickName },
  }));
  if (typeof data.error === "string") throw new Error(data.error);
  if (!Array.isArray(data.tools)) throw new Error("MCP returned no tool inventory.");
  return data.tools.flatMap((raw) => {
    if (!raw || typeof raw !== "object") return [];
    const tool = raw as Record<string, unknown>;
    if (typeof tool.name !== "string") return [];
    return [{ name: tool.name, description: typeof tool.description === "string" ? tool.description : "",
      category: typeof tool.category === "string" ? tool.category : null }];
  });
}

/** Re-discover bricks, Agent registries, and external servers without a restart. */
export async function reloadCapabilities(): Promise<Record<string, unknown>> {
  const client = await getMcpClient();
  return dataFrom(await client.callTool({ name: "reload_capabilities", arguments: {} }));
}
