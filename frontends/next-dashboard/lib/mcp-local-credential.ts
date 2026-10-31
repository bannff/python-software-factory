import { closeSync, constants, existsSync, fstatSync, openSync, readSync } from "node:fs";
import path from "node:path";

/**
 * Local MCP credential resolution.
 *
 * The launcher (`scripts/companion-x-ui.sh`) mints an ephemeral token and
 * exports it into its own shell, so a second process (a hand-started
 * `next dev`, a smoke stack, an agent) cannot join a running API. The launcher
 * therefore also persists that token to a `0600` file, and this module falls
 * back to reading it. The ambient `MCP_LOCAL_AUTH_TOKEN` stays the
 * higher-precedence source; set `MCP_LOCAL_TOKEN_FILE` to point somewhere else.
 *
 * Server-only: imports `node:fs` and is used exclusively by the local BFF.
 */

export const LOCAL_TOKEN_PATTERN = /^[A-Za-z0-9._~-]{16,512}$/;

const TOKEN_FILE_ENV = "MCP_LOCAL_TOKEN_FILE";
const TOKEN_FILE_RELATIVE = path.join("projects", "companion_x", ".storage", "local-mcp-token");
const MAX_ROOT_WALK = 8;
const MAX_TOKEN_FILE_BYTES = 1024;

export type LocalCredentialSource = "environment" | "file";

export interface LocalCredential {
  token: string;
  source: LocalCredentialSource;
}

export interface LocalMcpAuthorization {
  headers: Record<string, string>;
  /** Local auth is required but neither source produced a usable token. */
  missing: boolean;
}

/** Whether the local API expects a bearer token at all. */
export function localMcpAuthEnabled(): boolean {
  return ["1", "true", "yes"].includes((process.env.MCP_LOCAL_AUTH ?? "").toLowerCase());
}

function findRepoRoot(start: string): string | null {
  let current = path.resolve(start);
  for (let depth = 0; depth <= MAX_ROOT_WALK; depth += 1) {
    if (existsSync(path.join(current, "projects", "companion_x"))) return current;
    const parent = path.dirname(current);
    if (parent === current) return null;
    current = parent;
  }
  return null;
}

/** Path of the launcher-persisted token file, or `null` when it cannot be located. */
export function localTokenFilePath(): string | null {
  const override = process.env[TOKEN_FILE_ENV];
  if (override) return path.resolve(override);
  const root = findRepoRoot(process.cwd());
  return root === null ? null : path.join(root, TOKEN_FILE_RELATIVE);
}

/** Repo-relative path for server-side diagnostics — never the absolute layout. */
export function localTokenFileDisplayPath(): string {
  const file = localTokenFilePath();
  if (file === null) return "not located";
  const root = findRepoRoot(process.cwd());
  const relative = root === null ? null : path.relative(root, file);
  return relative === null || relative.startsWith("..") ? path.basename(file) : relative;
}

/**
 * A token file is trusted only when it is a regular file, no other user can
 * read it, and it is small. The descriptor is opened without following
 * symlinks and with `O_NONBLOCK` — a FIFO at this path would otherwise block
 * the open — then inspected with `fstat`, so the checks and the read cannot
 * disagree about which file they saw. `O_NONBLOCK` is inert for the regular
 * file the happy path reads.
 */
function readTokenFile(file: string): string | null {
  let descriptor: number;
  try {
    descriptor = openSync(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  } catch {
    return null;
  }
  try {
    const stats = fstatSync(descriptor);
    if (!stats.isFile() || (stats.mode & 0o077) !== 0 || stats.size > MAX_TOKEN_FILE_BYTES) {
      return null;
    }
    const buffer = Buffer.alloc(stats.size);
    const read = readSync(descriptor, buffer, 0, stats.size, 0);
    const token = buffer.subarray(0, read).toString("utf8").trim();
    return LOCAL_TOKEN_PATTERN.test(token) ? token : null;
  } catch {
    return null;
  } finally {
    closeSync(descriptor);
  }
}

/** Environment variable first, then the launcher-persisted file. */
export function resolveLocalCredential(): LocalCredential | null {
  const ambient = process.env.MCP_LOCAL_AUTH_TOKEN ?? "";
  if (LOCAL_TOKEN_PATTERN.test(ambient)) return { token: ambient, source: "environment" };
  const file = localTokenFilePath();
  if (file === null) return null;
  const token = readTokenFile(file);
  return token === null ? null : { token, source: "file" };
}

/**
 * Authorization for server-side AG-UI calls. Resolved on every call so a token
 * file written (or removed) after module import is honoured, and `missing`
 * lets the caller fail closed instead of sending an unauthenticated request.
 */
export function localMcpAuthorization(): LocalMcpAuthorization {
  if (!localMcpAuthEnabled()) return { headers: {}, missing: false };
  const credential = resolveLocalCredential();
  return credential === null
    ? { headers: {}, missing: true }
    : { headers: { authorization: `Bearer ${credential.token}` }, missing: false };
}
