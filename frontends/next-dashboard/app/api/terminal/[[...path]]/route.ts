import { NextRequest, NextResponse } from "next/server";
import { proxyLocalApi } from "@/lib/mcp-local-bff";
import { hasUnsafeSegment } from "@/lib/terminal-path-guard";

type Context = { params: Promise<{ path?: string[] }> };

async function proxy(req: NextRequest, context: Context): Promise<NextResponse> {
  const { path = [] } = await context.params;
  if (hasUnsafeSegment(path)) {
    return NextResponse.json(
      { detail: "Terminal path segment is not allowed" },
      { status: 400, headers: { "cache-control": "private, no-store, max-age=0" } },
    );
  }
  return proxyLocalApi(req, `/api/terminal/${path.join("/")}`);
}

export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
