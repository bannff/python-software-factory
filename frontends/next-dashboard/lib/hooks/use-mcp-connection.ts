"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";
import { getMcpClient, retryMcpConnection } from "@/lib/mcp-client";
import {
  getMcpConnectionState,
  subscribeMcpConnection,
} from "@/lib/mcp-connection-status";

export function useMcpConnection() {
  const { status, error } = useSyncExternalStore(
    subscribeMcpConnection,
    getMcpConnectionState,
    getMcpConnectionState,
  );

  // The rejection is swallowed here on purpose: `getMcpClient` records the
  // cause in the connection store before throwing, so the message reaches the
  // UI through `error` rather than an unhandled rejection.
  useEffect(() => {
    if (status === "idle") void getMcpClient().catch(() => undefined);
  }, [status]);

  const retry = useCallback(() => {
    void retryMcpConnection().catch(() => undefined);
  }, []);

  return { status, ready: status === "connected", error, retry };
}
