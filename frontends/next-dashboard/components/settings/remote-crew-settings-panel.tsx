import { CloudOff, Laptop } from "lucide-react";

export default function RemoteCrewSettingsPanel() {
  return <section aria-labelledby="remote-crew-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="remote-crew-settings-title" className="text-sm font-semibold">Remote Crew</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">See whether this workspace can connect to Companion X instances running on other machines.</p>
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <article className="rounded-md border border-border/40 p-4"><Laptop className="h-5 w-5 text-emerald-400" />
        <h3 className="mt-3 text-sm font-medium">This device</h3><p className="mt-1 text-xs text-muted-foreground">The current Companion X workspace runs locally on this device.</p>
        <span className="mt-4 inline-flex rounded-full bg-emerald-500/10 px-2 py-1 text-[10px] font-medium text-emerald-300">Available</span></article>
      <article className="rounded-md border border-border/40 p-4"><CloudOff className="h-5 w-5 text-muted-foreground" />
        <h3 className="mt-3 text-sm font-medium">Remote instances</h3><p className="mt-1 text-xs text-muted-foreground">No remote Companion X instances can be discovered, created, or connected in this version.</p>
        <span className="mt-4 inline-flex rounded-full bg-muted px-2 py-1 text-[10px] font-medium text-muted-foreground">Unavailable</span></article>
    </div>
    <p className="mt-4 rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">Creating and managing remote Companion X instances is not available here.</p>
  </section>;
}
