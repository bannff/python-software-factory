"use client";

import { useEffect, useState } from "react";
import { FlaskConical } from "lucide-react";
import { callTool } from "@/lib/api";
import { useMounted } from "@/lib/hooks/use-mounted";
import { unwrapToolData } from "@/lib/tool-result-data";

/** Persistent honesty strip: with the mock adapter, "provisioning" creates a placeholder, not a container. */
export function SandboxBanner() {
  const [mock, setMock] = useState(false);
  const mounted = useMounted();
  useEffect(() => {
    void callTool("sandbox_get_dashboard_summary")
      .then((raw) => {
        const data = unwrapToolData(raw) as { overview?: { adapter?: unknown } } | null;
        if (mounted.current) setMock(data?.overview?.adapter === "mock");
      })
      .catch(() => { /* unknown adapter: say nothing rather than guess */ });
  }, [mounted]);
  if (!mock) return null;
  return (
    <div role="note" className="flex items-center gap-2 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-300">
      <FlaskConical className="h-3.5 w-3.5 shrink-0" aria-hidden />
      <span><strong className="font-medium">Simulated environment.</strong> The mock adapter is active, so no containers run and environments are placeholders.</span>
    </div>
  );
}
