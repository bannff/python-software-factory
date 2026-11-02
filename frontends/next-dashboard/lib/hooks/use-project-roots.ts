"use client";

import { useEffect, useState } from "react";
import { callTool } from "@/lib/api";
import { parseAllowedRoots } from "@/lib/project-roots";

/**
 * Allowed project roots from the devtools brick. An unreadable list degrades
 * to empty so callers fall back to free-text entry instead of blocking.
 */
export function useProjectRoots(): { roots: string[]; loading: boolean } {
  const [roots, setRoots] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let live = true;
    callTool("devtools_list_allowed_project_roots", {})
      .then((raw) => { if (live) setRoots(parseAllowedRoots(raw)); })
      .catch(() => { if (live) setRoots([]); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);
  return { roots, loading };
}
