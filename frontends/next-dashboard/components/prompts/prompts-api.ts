import { getMcpClient } from "@/lib/mcp-client";

export interface PromptArgument {
  name: string;
  description: string;
  required: boolean;
}

export interface FactoryPrompt {
  brick: string;
  name: string;
  description: string;
  arguments: PromptArgument[];
}

export interface PromptCatalog {
  prompts: FactoryPrompt[];
  failedBricks: string[];
}

export interface RenderedPromptMessage {
  role: string;
  content: string;
}

function dataFrom(raw: unknown): Record<string, unknown> {
  if (!raw || typeof raw !== "object") throw new Error("MCP returned an invalid response.");
  const structured = (raw as { structuredContent?: unknown }).structuredContent;
  if (!structured || typeof structured !== "object") throw new Error("MCP returned no structured data.");
  const envelope = structured as { ok?: boolean; data?: unknown; error?: unknown };
  if (envelope.ok !== true || !envelope.data || typeof envelope.data !== "object") {
    throw new Error(typeof envelope.error === "string" ? envelope.error : "MCP operation failed.");
  }
  return envelope.data as Record<string, unknown>;
}

function argumentFrom(raw: unknown): PromptArgument | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  if (typeof value.name !== "string") return null;
  return {
    name: value.name,
    description: typeof value.description === "string" ? value.description : "",
    required: value.required === true,
  };
}

function promptFrom(brick: string, raw: unknown): FactoryPrompt | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  if (typeof value.name !== "string") return null;
  return {
    brick,
    name: value.name,
    description: typeof value.description === "string" ? value.description : "",
    arguments: Array.isArray(value.arguments)
      ? value.arguments.map(argumentFrom).filter((item): item is PromptArgument => item !== null)
      : [],
  };
}

export async function listFactoryPrompts(): Promise<PromptCatalog> {
  const client = await getMcpClient();
  const inventory = dataFrom(await client.callTool({ name: "list_bricks", arguments: {} }));
  if (!Array.isArray(inventory.bricks)) throw new Error("MCP returned no brick inventory.");
  const bricks = inventory.bricks.flatMap((raw) => {
    if (!raw || typeof raw !== "object") return [];
    const value = raw as Record<string, unknown>;
    return typeof value.name === "string" && value.healthy !== false ? [value.name] : [];
  });
  const results = await Promise.allSettled(bricks.map(async (brick) => {
    const data = dataFrom(await client.callTool({
      name: "get_brick_prompts", arguments: { brick_name: brick },
    }));
    if (typeof data.error === "string") throw new Error(data.error);
    if (!Array.isArray(data.prompts)) throw new Error("MCP returned no prompt inventory.");
    return data.prompts.map((raw) => promptFrom(brick, raw))
      .filter((item): item is FactoryPrompt => item !== null);
  }));
  const prompts = results.flatMap((result) => result.status === "fulfilled" ? result.value : [])
    .sort((a, b) => a.brick.localeCompare(b.brick) || a.name.localeCompare(b.name));
  const failedBricks = bricks.filter((_, index) => results[index].status === "rejected");
  return { prompts, failedBricks };
}

export async function renderFactoryPrompt(
  prompt: FactoryPrompt,
  argumentsByName: Record<string, string>,
): Promise<RenderedPromptMessage[]> {
  const client = await getMcpClient();
  const supplied = Object.fromEntries(
    Object.entries(argumentsByName).filter(([, value]) => value.trim() !== ""),
  );
  const data = dataFrom(await client.callTool({
    name: "render_brick_prompt",
    arguments: {
      brick_name: prompt.brick,
      prompt_name: prompt.name,
      arguments: JSON.stringify(supplied),
    },
  }));
  if (typeof data.error === "string") throw new Error(data.error);
  if (!Array.isArray(data.messages)) throw new Error("MCP returned no rendered prompt messages.");
  return data.messages.flatMap((raw) => {
    if (!raw || typeof raw !== "object") return [];
    const value = raw as Record<string, unknown>;
    return typeof value.role === "string" && typeof value.content === "string"
      ? [{ role: value.role, content: value.content }]
      : [];
  });
}
