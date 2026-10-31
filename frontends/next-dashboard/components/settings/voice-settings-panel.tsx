"use client";
import { MicOff, Volume2 } from "lucide-react";
import { useEffect, useState } from "react";

export default function VoiceSettingsPanel() {
  const [voiceCount, setVoiceCount] = useState<number | null>(null);
  useEffect(() => {
    if (!("speechSynthesis" in window)) { setVoiceCount(0); return; }
    const refresh = () => setVoiceCount(window.speechSynthesis.getVoices().length);
    refresh();
    window.speechSynthesis.addEventListener("voiceschanged", refresh);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", refresh);
  }, []);
  const readAloud = voiceCount === null ? "Checking…"
    : voiceCount > 0 ? `Available · ${voiceCount} system voice${voiceCount === 1 ? "" : "s"}`
      : "Unavailable in this browser";
  return <section aria-labelledby="voice-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="voice-settings-title" className="text-sm font-semibold">Voice</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">Current read-aloud and dictation availability.</p>
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <article className="rounded-md border border-border/40 p-4"><Volume2 className="h-5 w-5 text-violet-400" />
        <h3 className="mt-3 text-sm font-medium">Read aloud</h3><p className="mt-1 text-xs text-muted-foreground">Assistant messages can use your browser’s built-in speech voices.</p>
        <span className="mt-4 inline-flex rounded-full bg-muted px-2 py-1 text-[10px] text-muted-foreground">{readAloud}</span></article>
      <article className="rounded-md border border-border/40 p-4"><MicOff className="h-5 w-5 text-muted-foreground" />
        <h3 className="mt-3 text-sm font-medium">Dictation</h3><p className="mt-1 text-xs text-muted-foreground">Microphone access is disabled by this dashboard’s security policy.</p>
        <span className="mt-4 inline-flex rounded-full bg-muted px-2 py-1 text-[10px] text-muted-foreground">Disabled</span></article>
    </div>
    <p className="mt-4 rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">Choosing a preferred voice or dictation engine is not available. Read aloud uses the browser’s current default voice.</p>
  </section>;
}
