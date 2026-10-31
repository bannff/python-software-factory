import { Bug, FlaskConical, Network } from "lucide-react";
import { LocalStorageInspector } from "./local-storage-inspector";
import { McpPoolPanel } from "./mcp-pool-panel";
import { DebugToolsPanel } from "./debug-tools-panel";
import { SystemPanel } from "./system-panel";
import { TelemetryPanel } from "./telemetry-panel";
import { LogsPanel } from "./logs-panel";
import { MemoryStatsPanel } from "./memory-stats-panel";
import { ConfigPanel } from "./config-panel";
import { AgentBackendPanel } from "./agent-backend-panel";

const STATUS = [
  { icon: Bug, title: "Developer tools", detail: "Debugging tools appear automatically when supported. Open Web Inspector from the bottom bar." },
  { icon: FlaskConical, title: "Feature previews", detail: "This dashboard has no personal preview list or switches. Experimental service features are chosen outside the dashboard." },
  { icon: Network, title: "API connection", detail: "The dashboard server chooses its Companion X API address when it starts. It cannot be switched from this page." },
] as const;

export default function DeveloperSettingsPanel() {
  return <section aria-labelledby="developer-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="developer-settings-title" className="text-sm font-semibold">Developer</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">Current debugging, preview, and connection behavior.</p>
    <div className="mt-4 grid gap-3 sm:grid-cols-3">{STATUS.map((item) => <article key={item.title} className="rounded-md border border-border/40 p-4">
      <item.icon className="h-5 w-5 text-violet-400" /><h3 className="mt-3 text-sm font-medium">{item.title}</h3>
      <p className="mt-1 text-xs text-muted-foreground">{item.detail}</p>
    </article>)}</div>
    <SystemPanel />
    <AgentBackendPanel />
    <ConfigPanel />
    <TelemetryPanel />
    <LogsPanel />
    <McpPoolPanel />
    <MemoryStatsPanel />
    <DebugToolsPanel />
    <LocalStorageInspector />
    <p className="mt-4 rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">Developer Mode, feature-preview opt-ins, and a local/remote gateway switch are not available as user settings.</p>
  </section>;
}
