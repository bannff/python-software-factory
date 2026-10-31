import { NextRequest } from "next/server";
import { proxyLocalMcp } from "@/lib/mcp-local-bff";

/**
 * Local-only BFF for the native MCP Streamable-HTTP surface.
 *
 * Browser JavaScript carries no bearer. The route admits only guarded,
 * same-origin loopback traffic and projects the server-side local credential
 * to the fixed backend `/mcp/` endpoint. Python Auth and Permissions remain
 * authoritative for every discovery and execution request.
 */
export async function GET(req: NextRequest) {
  return proxyLocalMcp(req);
}

export async function POST(req: NextRequest) {
  return proxyLocalMcp(req);
}

export async function DELETE(req: NextRequest) {
  return proxyLocalMcp(req);
}
