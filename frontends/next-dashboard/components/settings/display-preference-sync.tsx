"use client";
import { useEffect, useRef } from "react";
import { useTheme } from "next-themes";
import { useDisplayPreferences } from "./use-display-preferences";

/**
 * Apply the durable Display preferences once loaded and whenever they change:
 * theme via next-themes, density as `data-density` on <html> (drives the
 * compact spacing scale in globals.css), and language as `<html lang>` so
 * locale-aware formatting and assistive tech follow the owner's choice.
 */
export default function DisplayPreferenceSync() {
  const { setTheme } = useTheme();
  const { preferences, loading } = useDisplayPreferences();
  // next-themes recreates `setTheme` on its own state changes; keying the
  // effect on it re-applied the saved theme right after a toggle (flash +
  // revert). Track the latest setter and react only to the durable theme.
  const apply = useRef(setTheme);
  apply.current = setTheme;
  useEffect(() => {
    if (!loading) apply.current(preferences.theme);
  }, [loading, preferences.theme]);
  useEffect(() => {
    if (loading) return;
    const root = document.documentElement;
    root.dataset.density = preferences.density;
    root.lang = preferences.language;
  }, [loading, preferences.density, preferences.language]);
  return null;
}
