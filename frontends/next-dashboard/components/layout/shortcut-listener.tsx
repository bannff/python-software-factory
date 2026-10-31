"use client";

import { useEffect } from "react";
import { useDisplayPreferences } from "@/components/settings/use-display-preferences";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { effectiveChord, matchesChord } from "@/lib/shortcuts";

/** Ignore chords typed into editable fields unless a modifier is held. */
function inEditable(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

/**
 * Global consumer for owner-remappable workbench shortcuts (chat + Terminal
 * toggles). The command palette binds its own chord the same way.
 */
export function ShortcutListener() {
  const { toggleChat, toggleTerminal } = useWorkbenchContext();
  const { preferences } = useDisplayPreferences();
  useEffect(() => {
    const chat = effectiveChord("toggle_chat", preferences.shortcuts);
    const terminal = effectiveChord("toggle_terminal", preferences.shortcuts);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.repeat || event.isComposing) return;
      if (!(event.metaKey || event.ctrlKey || event.altKey) && inEditable(event.target)) return;
      if (chat && matchesChord(event, chat)) { event.preventDefault(); toggleChat(); }
      else if (terminal && matchesChord(event, terminal)) { event.preventDefault(); toggleTerminal(); }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [preferences.shortcuts, toggleChat, toggleTerminal]);
  return null;
}
