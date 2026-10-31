"use client";
import { useCallback, useEffect, useState } from "react";
import { getChatPreferences, type ChatPreferences } from "./chat-preferences-api";

const EVENT = "companion-x-chat-preferences";
const DEFAULTS: ChatPreferences = {
  plainDiffs: false, hiddenModels: [], defaultMemoryMode: "persistent",
  collapseMessageInput: false, pinLatestPrompt: false, revision: 0,
};

export function announceChatPreferences(value: ChatPreferences): void {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(EVENT, { detail: value }));
}

export function useChatPreferences() {
  const [preferences, setPreferences] = useState(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    setLoading(true);
    try { setPreferences(await getChatPreferences()); setError(null); }
    catch { setError("Chat preferences unavailable"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const receive = (event: Event) => setPreferences((event as CustomEvent<ChatPreferences>).detail);
    window.addEventListener(EVENT, receive);
    return () => window.removeEventListener(EVENT, receive);
  }, []);
  return { preferences, loading, error, refresh };
}
