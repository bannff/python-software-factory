import { NextRequest } from "next/server";
import { proxyRequest } from "@/lib/proxy";

/** Runtime proxy for /ag-ui/* requests (AG-UI protocol). */

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, (await params).path, "ag-ui");
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, (await params).path, "ag-ui");
}
