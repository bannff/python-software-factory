"use client";
import { Activity, Boxes, GitCommitHorizontal, PackageOpen, Wrench } from "lucide-react";
import packageInfo from "../../package.json";
import { useHealth } from "@/lib/hooks/use-health";
import { getBuildId } from "@/lib/build-info";
import DiagnosticsBundlePanel from "./diagnostics-bundle-panel";

export default function AboutSettingsPanel() {
  const health = useHealth();
  const items = [
    { icon: PackageOpen, label: "Dashboard version", value: packageInfo.version },
    { icon: GitCommitHorizontal, label: "Build", value: getBuildId() },
    { icon: Activity, label: "API status", value: health.status },
    { icon: Boxes, label: "Installed capabilities", value: health.brickCount ?? "Unavailable" },
    { icon: Wrench, label: "Available tools", value: health.totalTools ?? "Unavailable" },
  ];
  return <section aria-labelledby="about-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="about-settings-title" className="text-sm font-semibold">About</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">Version and live connection information for this Companion X dashboard.</p>
    <dl className="mt-4 grid gap-3 sm:grid-cols-2">{items.map((item) => <div key={item.label} className="flex items-center gap-3 rounded-md border border-border/40 p-4">
      <item.icon className="h-5 w-5 shrink-0 text-violet-400" /><div><dt className="text-[10px] uppercase tracking-wider text-muted-foreground">{item.label}</dt>
        <dd className="mt-1 text-sm font-medium capitalize">{item.value}</dd></div>
    </div>)}</dl>
    <DiagnosticsBundlePanel />
    <p className="mt-4 rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">The build identifier is set by the release pipeline (<code>NEXT_PUBLIC_BUILD_ID</code>) and shows &ldquo;development&rdquo; for local runs. A report-problem workflow is not available in this dashboard.</p>
  </section>;
}
