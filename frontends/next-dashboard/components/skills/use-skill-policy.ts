"use client";

import { useCallback, useEffect, useState } from "react";
import { getSkillPolicy, updateSkillPolicy, type SkillPolicy } from "./skills-api";

const EVENT = "companion-x-skill-policy";

/** Owner-scoped skill enablement; every subscriber converges on a saved policy. */
export function useSkillPolicy() {
  const [policy, setPolicy] = useState<SkillPolicy>({ disabledSkills: [], revision: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { setPolicy(await getSkillPolicy()); setError(null); }
    catch { setError("Skill policy unavailable"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const receive = (event: Event) => setPolicy((event as CustomEvent<SkillPolicy>).detail);
    window.addEventListener(EVENT, receive);
    return () => window.removeEventListener(EVENT, receive);
  }, []);

  const setDisabled = useCallback(async (skillId: string, disabled: boolean) => {
    const next = disabled
      ? Array.from(new Set([...policy.disabledSkills, skillId]))
      : policy.disabledSkills.filter((item) => item !== skillId);
    const saved = await updateSkillPolicy(next, policy.revision);
    window.dispatchEvent(new CustomEvent(EVENT, { detail: saved }));
    return saved;
  }, [policy]);

  return { policy, loading, error, refresh, setDisabled };
}
