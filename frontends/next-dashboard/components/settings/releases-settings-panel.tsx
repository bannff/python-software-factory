"use client";
import { GitBranch, PackageOpen, Rocket } from "lucide-react";
import packageInfo from "../../package.json";
import { getBuildId } from "@/lib/build-info";

/**
 * Row 100 (feature-map) — `releases`. Re-spec'd against Companion-X's own
 * release story (owner 2026-09-14: "release sounds core… re-spec").
 *
 * Upstream KiroCrew shipped an auto-updating desktop app with a release
 * channel + in-app update check + changelog (`GET /api/update/check`,
 * `/api/releases`, `/api/changelog`). Companion-X on this port has NO such
 * update service — the dashboard is updated by redeploying the gateway, not
 * by an in-app updater. So this panel honestly surfaces what IS real (the
 * running version + build identifier, row 101's `NEXT_PUBLIC_BUILD_ID`) and
 * discloses that the release-channel / update-check / changelog controls are
 * not part of this deployment, rather than faking an update button.
 */
export default function ReleasesSettingsPanel() {
  const items = [
    { icon: PackageOpen, label: "Dashboard version", value: packageInfo.version },
    { icon: GitBranch, label: "Build", value: getBuildId() },
  ];
  return (
    <section aria-labelledby="releases-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
      <h2 id="releases-settings-title" className="flex items-center gap-2 text-sm font-semibold">
        <Rocket className="h-4 w-4 text-violet-400" /> Releases
      </h2>
      <p className="mt-0.5 text-xs text-muted-foreground">The running build of this Companion X dashboard.</p>
      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-3 rounded-md border border-border/40 p-4">
            <item.icon className="h-5 w-5 shrink-0 text-violet-400" />
            <div>
              <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">{item.label}</dt>
              <dd className="mt-1 text-sm font-medium capitalize">{item.value}</dd>
            </div>
          </div>
        ))}
      </dl>
      <p className="mt-4 rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">
        This dashboard updates by redeploying the gateway — there is no in-app release channel,
        update check, or changelog service on this deployment. The build identifier above (set by
        the release pipeline via <code>NEXT_PUBLIC_BUILD_ID</code>) is how a running build is pinned.
      </p>
    </section>
  );
}
