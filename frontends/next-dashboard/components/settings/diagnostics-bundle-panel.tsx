"use client";
import { useState } from "react";
import { Download } from "lucide-react";
import { useHealth } from "@/lib/hooks/use-health";
import packageInfo from "../../package.json";

/** Row 101 (feature-map): a downloadable diagnostics bundle — version,
 * live health, and basic runtime context, composed entirely from data
 * this panel already fetches. No new backend endpoint: nothing here is
 * server-stored, matching row 102's own "host-side file" pattern. Never
 * includes secrets, credentials, or conversation content — only the
 * same connection/health facts already visible on this page. */
export default function DiagnosticsBundlePanel() {
  const health = useHealth();
  const [notice, setNotice] = useState<string | null>(null);

  const download = () => {
    const bundle = {
      generated_at: new Date().toISOString(),
      dashboard_version: packageInfo.version,
      api_status: health.status,
      registered_capabilities: health.brickCount,
      healthy_capabilities: health.healthyBricks,
      available_tools: health.totalTools,
      user_agent: typeof navigator === "undefined" ? "unknown" : navigator.userAgent,
      dashboard_url: typeof window === "undefined" ? "unknown" : window.location.origin,
    };
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = `companion-x-diagnostics-${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
    setNotice("Diagnostics bundle downloaded.");
  };

  return <div className="mt-4">
    {notice && <p role="status" className="mb-3 rounded-md border border-emerald-500/30 bg-emerald-500/5 p-3 text-xs text-emerald-200">{notice}</p>}
    <button type="button" onClick={download}
      className="inline-flex items-center gap-2 rounded-md border border-border/60 px-3 py-2 text-xs hover:bg-muted/40">
      <Download className="h-3.5 w-3.5" />Download diagnostics bundle</button>
    <p className="mt-2 text-[11px] text-muted-foreground">Version, live health, and connection status only — never conversation content or credentials.</p>
  </div>;
}
