"use client";

import { useState } from "react";
import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
import { updateDisplayPreferences } from "@/components/settings/display-preferences-api";
import {
  announceDisplayPreferences, useDisplayPreferences,
} from "@/components/settings/use-display-preferences";

/**
 * The durable Display preference is the source of truth for theme;
 * `DisplayPreferenceSync` re-applies it. A toggle that only called
 * `next-themes.setTheme` flashed and reverted. The toggle therefore writes
 * the full preference object (CAS on revision), announces the saved value so
 * every subscriber converges, and only then applies it to next-themes.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const { preferences, loading, refresh } = useDisplayPreferences();
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    const theme = resolvedTheme === "dark" ? "light" : "dark";
    setBusy(true);
    try {
      const saved = await updateDisplayPreferences({ ...preferences, theme });
      announceDisplayPreferences(saved);
      setTheme(saved.theme);
    } catch {
      void refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      onClick={() => void toggle()}
      disabled={busy || loading}
      aria-label="Toggle theme"
      aria-busy={busy}
      className="relative flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:text-foreground transition-colors disabled:opacity-60"
    >
      <Sun className="h-3.5 w-3.5 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute h-3.5 w-3.5 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
    </button>
  );
}
