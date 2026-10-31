"use client";
import { useCallback, useEffect, useState } from "react";
import { getDisplayPreferences, type DisplayPreferences } from "./display-preferences-api";
const EVENT = "companion-x-display-preferences";
const DEFAULTS: DisplayPreferences = {
  theme: "system", terminalFontSize: 11, terminalShell: null,
  terminalCompletionEnabled: true, density: "comfortable", language: "en", shortcuts: {}, revision: 0,
};
export function announceDisplayPreferences(value: DisplayPreferences) {
  window.dispatchEvent(new CustomEvent(EVENT, { detail: value }));
}
export function useDisplayPreferences() {
  const [preferences, setPreferences] = useState(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    setLoading(true);
    try { setPreferences(await getDisplayPreferences()); setError(null); }
    catch { setError("Display preferences unavailable"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const receive = (event: Event) => setPreferences((event as CustomEvent<DisplayPreferences>).detail);
    window.addEventListener(EVENT, receive);
    return () => window.removeEventListener(EVENT, receive);
  }, []);
  return { preferences, loading, error, refresh };
}
