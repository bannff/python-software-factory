"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";
import ImportPanel from "@/components/settings/import-panel";
import ChatPreferencesPanel from "@/components/settings/chat-preferences-panel";
import DisplayPreferencesPanel from "@/components/settings/display-preferences-panel";
import NotificationSettingsPanel from "@/components/settings/notification-settings-panel";
import ShortcutsPanel from "@/components/settings/shortcuts-panel";
import SkillsSettingsPanel from "@/components/settings/skills-settings-panel";
import ChannelsSettingsPanel from "@/components/settings/channels-settings-panel";
import BrowserSettingsPanel from "@/components/settings/browser-settings-panel";
import ComputerUseSettingsPanel from "@/components/settings/computer-use-settings-panel";
import RemoteCrewSettingsPanel from "@/components/settings/remote-crew-settings-panel";
import PrivacySettingsPanel from "@/components/settings/privacy-settings-panel";
import SecuritySettingsPanel from "@/components/settings/security-settings-panel";
import SecretsSettingsPanel from "@/components/settings/secrets-settings-panel";
import DeveloperSettingsPanel from "@/components/settings/developer-settings-panel";
import AboutSettingsPanel from "@/components/settings/about-settings-panel";
import ReleasesSettingsPanel from "@/components/settings/releases-settings-panel";
import VoiceSettingsPanel from "@/components/settings/voice-settings-panel";
import OverviewPanel from "@/components/settings/overview-panel";
import UsageSettingsPanel from "@/components/settings/usage-settings-panel";

/** One Settings destination with the complete M7.5 section inventory. */
const TABS = [
  { id: "overview", label: "Overview" }, { id: "imports", label: "Import & Export" },
  { id: "chat", label: "Chat" }, { id: "display", label: "Display" },
  { id: "voice", label: "Voice" }, { id: "notifications", label: "Notifications" },
  { id: "shortcuts", label: "Shortcuts" }, { id: "skills", label: "Skills" },
  { id: "channels", label: "Channels" }, { id: "browser", label: "Browser" },
  { id: "computer-use", label: "Computer Use" }, { id: "remote-crew", label: "Remote Crew" },
  { id: "privacy", label: "Privacy" }, { id: "security", label: "Security" },
  { id: "secrets", label: "Secrets" }, { id: "usage", label: "Usage" },
  { id: "developer", label: "Developer" }, { id: "about", label: "About" },
  { id: "releases", label: "Releases" },
] as const;

type TabId = (typeof TABS)[number]["id"];
const IDS = new Set<string>(TABS.map((tab) => tab.id));

export default function SettingsView() {
  const requested = useSearchParams().get("section");
  const [active, setActive] = useState<TabId>(
    requested && IDS.has(requested) ? requested as TabId : "overview",
  );
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  useEffect(() => {
    if (requested && IDS.has(requested)) setActive(requested as TabId);
  }, [requested]);
  const select = (id: TabId) => {
    setActive(id);
    window.history.pushState({}, "", `/settings?section=${id}`);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = TABS.findIndex((tab) => tab.id === active);
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % TABS.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + TABS.length) % TABS.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = TABS.length - 1;
    else return;
    event.preventDefault();
    const target = TABS[next].id;
    select(target);
    refs.current[target]?.focus();
  };

  return (
    <section
      aria-labelledby="settings-title"
      className="mx-auto flex min-h-full w-full max-w-5xl flex-col gap-6 p-6"
    >
      <header>
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-400">Workspace</p>
        <h1 id="settings-title" className="mt-1 text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Review your current Companion X configuration.
        </p>
      </header>

      <div
        role="tablist"
        aria-label="Settings sections"
        aria-orientation="horizontal"
        onKeyDown={onKeyDown}
        className="flex flex-wrap gap-1 border-b border-border/50"
      >
        {TABS.map((tab) => {
          const selected = tab.id === active;
          return (
            <button
              key={tab.id}
              ref={(element) => { refs.current[tab.id] = element; }}
              role="tab"
              id={`settings-tab-${tab.id}`}
              type="button"
              aria-selected={selected}
              aria-controls={`settings-panel-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => select(tab.id)}
              className={cn(
                "-mb-px rounded-t-md border-b-2 px-4 py-2 text-sm font-medium transition-colors",
                selected
                  ? "border-violet-500 text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div
        role="tabpanel"
        id={`settings-panel-${active}`}
        aria-labelledby={`settings-tab-${active}`}
        tabIndex={0}
      >
        {active === "overview" && <OverviewPanel />}
        {active === "imports" && <ImportPanel />}
        {active === "chat" && <ChatPreferencesPanel />}
        {active === "display" && <DisplayPreferencesPanel />}
        {active === "voice" && <VoiceSettingsPanel />}
        {active === "notifications" && <NotificationSettingsPanel />}
        {active === "shortcuts" && <ShortcutsPanel />}
        {active === "skills" && <SkillsSettingsPanel />}
        {active === "channels" && <ChannelsSettingsPanel />}
        {active === "browser" && <BrowserSettingsPanel />}
        {active === "computer-use" && <ComputerUseSettingsPanel />}
        {active === "remote-crew" && <RemoteCrewSettingsPanel />}
        {active === "privacy" && <PrivacySettingsPanel />}
        {active === "security" && <SecuritySettingsPanel />}
        {active === "secrets" && <SecretsSettingsPanel />}
        {active === "usage" && <UsageSettingsPanel />}
        {active === "developer" && <DeveloperSettingsPanel />}
        {active === "about" && <AboutSettingsPanel />}
        {active === "releases" && <ReleasesSettingsPanel />}
      </div>
    </section>
  );
}
