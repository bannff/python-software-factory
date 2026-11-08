"use client";

import { useEffect, useState } from "react";
import { callTool } from "@/lib/api";
import { parseProjects } from "@/lib/project-roots";

/**
 * Admissible project directories (under the allowed roots, carrying a project
 * marker) from the devtools brick. An unreadable list degrades to empty so
 * callers fall back to free-text entry instead of blocking.
 */
export function useProjectDirectories(): { projects: string[]; loading: boolean } {
  const [projects, setProjects] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let live = true;
    callTool("devtools_list_projects", {})
      .then((raw) => { if (live) setProjects(parseProjects(raw)); })
      .catch(() => { if (live) setProjects([]); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);
  return { projects, loading };
}
