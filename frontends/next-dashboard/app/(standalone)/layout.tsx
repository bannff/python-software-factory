/**
 * Popout and embed routes: one surface, no workbench chrome. A route group
 * (not an overlay) so the nav rail, terminal dock and status bar are never
 * mounted at all.
 */
export default function StandaloneGroupLayout({ children }: { children: React.ReactNode }) {
  return <main className="flex h-screen flex-col overflow-hidden bg-background">{children}</main>;
}
