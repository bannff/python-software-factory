import { Topbar } from "@/components/layout/topbar";
import { StatusBar } from "@/components/layout/status-bar";
import TerminalDock from "@/components/terminal/terminal-dock";
import { ShortcutListener } from "@/components/layout/shortcut-listener";

/** The full workbench: nav chrome, terminal dock and status bar. */
export default function WorkbenchGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Topbar />
      <ShortcutListener />
      <main className="flex-1 min-h-0 overflow-hidden">{children}</main>
      <TerminalDock />
      <StatusBar />
    </div>
  );
}
