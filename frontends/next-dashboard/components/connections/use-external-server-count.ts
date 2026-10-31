"use client";

import { useEffect, useState } from "react";
import { useMcpConnection } from "@/lib/hooks/use-mcp-connection";
import { listExternalServers } from "./external-servers-api";

/** Registered / mounted external MCP server counts for at-a-glance surfaces. */
export function useExternalServerCount(): { count: number | null; mounted: number | null } {
  const { ready } = useMcpConnection();
  const [state, setState] = useState<{ count: number | null; mounted: number | null }>({ count: null, mounted: null });
  useEffect(() => {
    if (!ready) return;
    let live = true;
    listExternalServers()
      .then((servers) => { if (live) setState({ count: servers.length, mounted: servers.filter((s) => s.mounted).length }); })
      .catch(() => { if (live) setState({ count: null, mounted: null }); });
    return () => { live = false; };
  }, [ready]);
  return state;
}
