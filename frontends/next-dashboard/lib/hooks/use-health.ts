"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
import type { McpBrickHealth, TimelineCapabilities } from "@/lib/types";

interface HealthData {
  connected: boolean;
  status: string;
  gateway: string | null;
  totalTools: number | null;
  brickCount: number | null;
  healthyBricks: number | null;
  bricks: Record<string, McpBrickHealth>;
  timeline: TimelineCapabilities | null;
  lastChecked: number | null;
}

/**
 * Shared health polling hook — used by StatusBar and WelcomeView.
 * Polls every 30s. Now exposes per-brick health for the brick explorer popover.
 */
export function useHealth(): HealthData {
  const [data, setData] = useState<HealthData>({
    connected: false,
    status: "unknown",
    gateway: null,
    totalTools: null,
    brickCount: null,
    healthyBricks: null,
    bricks: {},
    timeline: null,
    lastChecked: null,
  });

  useEffect(() => {
    let mounted = true;
    async function poll() {
      try {
        const h = await getHealth();
        if (!mounted) return;
        setData({
          connected: h.status === "healthy",
          status: h.status,
          gateway: h.gateway ?? null,
          totalTools: h.capabilities?.total_tools ?? h.total_tools,
          brickCount: h.mcp_health?.total_bricks ?? null,
          healthyBricks: h.mcp_health?.healthy_bricks ?? null,
          bricks: h.mcp_health?.bricks ?? {},
          timeline: h.timeline ?? null,
          lastChecked: Date.now(),
        });
      } catch {
        if (!mounted) return;
        setData((prev) => ({
          ...prev,
          connected: false,
          status: "unhealthy",
          lastChecked: Date.now(),
        }));
      }
    }
    poll();
    const id = setInterval(poll, 30_000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  return data;
}
