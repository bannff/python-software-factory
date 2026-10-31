import { Bell, Cable, ArrowUpRight } from "lucide-react";

const DESTINATIONS = [
  { title: "Delivery channels", detail: "See where Companion X can send console, Slack, email, webhook, and SMS notifications.",
    href: "/settings?section=notifications", action: "Open Notifications", icon: Bell },
  { title: "Connected tools", detail: "See available tools and turn on the connections this workspace can use.",
    href: "/capabilities?tab=connections", action: "Open Connections", icon: Cable },
] as const;

export default function ChannelsSettingsPanel() {
  return <section aria-labelledby="channels-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="channels-settings-title" className="text-sm font-semibold">Channels</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">Choose where to manage message delivery and connected tools.</p>
    <div className="mt-4 grid gap-3 sm:grid-cols-2">{DESTINATIONS.map((item) => <article key={item.title} className="rounded-md border border-border/40 p-4">
      <item.icon className="h-5 w-5 text-violet-400" /><h3 className="mt-3 text-sm font-medium">{item.title}</h3>
      <p className="mt-1 min-h-10 text-xs text-muted-foreground">{item.detail}</p>
      <a href={item.href} className="mt-4 inline-flex items-center gap-2 text-xs font-medium text-violet-300 hover:text-violet-200">{item.action}<ArrowUpRight className="h-3.5 w-3.5" /></a>
    </article>)}</div>
    <p className="mt-4 rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">Provider account setup for Discord, Telegram, WhatsApp, and Teams is not available. Delivery credentials remain administrator-owned and are never exposed or rewritten here.</p>
  </section>;
}
