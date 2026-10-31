import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

/** Public projection of an owner-registered external MCP server — no secret values. */
export interface ExternalServer {
  name: string;
  transport: "stdio" | "streamable_http";
  command: string | null;
  args: string[];
  cwd: string | null;
  env: Record<string, string>;
  url: string | null;
  headers: Record<string, string>;
  enabled: boolean;
  mounted: boolean;
  unresolvedEnv: string[];
  toolsCount: number;
  revision: number;
}

/** Spec as written in an mcpServers document; env/headers map NAME → SOURCE_ENV_NAME. */
export interface ExternalServerSpec {
  transport: "stdio" | "streamable_http";
  command?: string;
  args?: string[];
  cwd?: string;
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
  enabled: boolean;
}

function namesFrom(raw: unknown): Record<string, string> {
  if (!raw || typeof raw !== "object") return {};
  return Object.fromEntries(Object.entries(raw as Record<string, unknown>)
    .filter((entry): entry is [string, string] => typeof entry[1] === "string"));
}

function serverFrom(raw: unknown): ExternalServer {
  if (!raw || typeof raw !== "object") throw new Error("Server unavailable.");
  const v = raw as Record<string, unknown>;
  if (typeof v.name !== "string" || typeof v.revision !== "number") throw new Error("Server unavailable.");
  return {
    name: v.name,
    transport: v.transport === "streamable_http" ? "streamable_http" : "stdio",
    command: typeof v.command === "string" ? v.command : null,
    args: Array.isArray(v.args) ? v.args.filter((a): a is string => typeof a === "string") : [],
    cwd: typeof v.cwd === "string" ? v.cwd : null,
    env: namesFrom(v.env),
    url: typeof v.url === "string" ? v.url : null,
    headers: namesFrom(v.headers),
    enabled: v.enabled === true,
    mounted: v.mounted === true,
    unresolvedEnv: Array.isArray(v.unresolved_env) ? v.unresolved_env.filter((a): a is string => typeof a === "string") : [],
    toolsCount: typeof v.tools_count === "number" ? v.tools_count : 0,
    revision: v.revision,
  };
}

function serversFrom(raw: unknown): ExternalServer[] {
  const data = unwrapToolData(raw) as { servers?: unknown };
  if (!Array.isArray(data.servers)) throw new Error("Servers unavailable.");
  return data.servers.map(serverFrom);
}

export async function listExternalServers(): Promise<ExternalServer[]> {
  return serversFrom(await callTool("connections_list_servers", {}));
}

export async function addExternalServer(name: string, spec: ExternalServerSpec): Promise<ExternalServer> {
  const data = unwrapToolData(await callTool("connections_add_server", { name, spec })) as { server?: unknown };
  return serverFrom(data.server);
}

export async function importExternalServers(document: string): Promise<ExternalServer[]> {
  return serversFrom(await callTool("connections_import_servers", { document }));
}

export async function updateExternalServer(
  name: string, spec: ExternalServerSpec, expectedRevision: number,
): Promise<ExternalServer> {
  const data = unwrapToolData(await callTool("connections_update_server", {
    name, spec, expected_revision: expectedRevision,
  })) as { server?: unknown };
  return serverFrom(data.server);
}

export async function removeExternalServer(name: string, expectedRevision: number): Promise<void> {
  unwrapToolData(await callTool("connections_remove_server", { name, expected_revision: expectedRevision }));
}

export async function reloadExternalServers(): Promise<Record<string, string>> {
  const data = unwrapToolData(await callTool("connections_reload", {})) as { outcome?: unknown };
  return data.outcome && typeof data.outcome === "object" ? data.outcome as Record<string, string> : {};
}

/** Rebuild the exact spec for enable/disable toggles from the public view. */
export function specFrom(server: ExternalServer, enabled: boolean): ExternalServerSpec {
  return server.transport === "stdio"
    ? { transport: "stdio", command: server.command ?? "", args: server.args,
        ...(server.cwd ? { cwd: server.cwd } : {}), env: server.env, enabled }
    : { transport: "streamable_http", url: server.url ?? "", headers: server.headers, enabled };
}
