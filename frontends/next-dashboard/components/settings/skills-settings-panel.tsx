"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, BookOpen } from "lucide-react";
import { listSkills, type SkillSummary } from "@/components/skills/skills-api";
import { useSkillPolicy } from "@/components/skills/use-skill-policy";

/**
 * Settings → Skills: per-skill enablement for this owner (durable, revision
 * CAS). Browse/create stays in Agent Capabilities → Skills. A disabled skill
 * is subtracted from every persona that lists it before the run's manifest
 * is frozen, so replay evidence shows exactly what attached.
 */
export default function SkillsSettingsPanel() {
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [listError, setListError] = useState<string | null>(null);
  const { policy, loading, error, refresh, setDisabled } = useSkillPolicy();
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => { void listSkills().then(setSkills).catch(() => setListError("Skills unavailable")); }, []);

  const toggle = async (skill: SkillSummary, enabled: boolean) => {
    setBusy(skill.id); setNotice(null);
    try { await setDisabled(skill.id, !enabled); }
    catch (cause) {
      const conflict = cause instanceof Error && cause.message.includes("conflict");
      setNotice(conflict ? "Skill settings changed elsewhere. Current values were reloaded." : "That change couldn’t be saved.");
      if (conflict) void refresh();
    } finally { setBusy(null); }
  };

  const disabled = new Set(policy.disabledSkills);
  return <section aria-labelledby="skills-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 id="skills-settings-title" className="text-sm font-semibold">Skills</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">Choose which skills your agents may use. Off means no persona attaches it for you.</p></div>
      <a href="/capabilities?tab=skills" className="inline-flex items-center gap-2 rounded-md border border-border/60 px-3 py-2 text-xs font-medium hover:bg-accent/40">
        <BookOpen className="h-3.5 w-3.5 text-violet-400" /> Browse or create <ArrowUpRight className="h-3.5 w-3.5" /></a>
    </div>
    {(error || listError || notice) && <p role="alert" className="mt-3 text-xs text-destructive">{notice || error || listError}</p>}
    {loading ? <p className="mt-4 text-xs text-muted-foreground">Loading skill settings…</p>
      : skills.length === 0 ? <p className="mt-4 text-xs text-muted-foreground">No skills are installed yet.</p>
      : <ul className="mt-4 divide-y divide-border/40 rounded-md border border-border/40">
        {skills.map((skill) => <li key={skill.id} className="flex items-center gap-3 p-3">
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{skill.name}</p>
            {skill.description && <p className="truncate text-xs text-muted-foreground">{skill.description}</p>}</div>
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" role="switch" aria-label={`Enable ${skill.name}`} checked={!disabled.has(skill.id)}
              disabled={busy !== null} onChange={(event) => void toggle(skill, event.target.checked)} />
            {disabled.has(skill.id) ? "Off" : "On"}
          </label>
        </li>)}
      </ul>}
    <p className="mt-4 rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">
      A per-skill context budget is not offered: Companion X attaches skills as files the agent opens on demand rather than injecting their text into every turn, so there is no injected text to cap.
    </p>
  </section>;
}
