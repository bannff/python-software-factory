"use client";

import { z } from "zod";
import { useFrontendTool } from "@copilotkit/react-core/v2";
import { useWorkbenchContext } from "@/lib/workbench-context";

const Args = z.object({
  slug: z.string().regex(/^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$/).optional(),
});

export function artifactPath(slug?: string): string {
  return slug ? `/artifacts/${encodeURIComponent(slug)}` : "/artifacts";
}

export function useArtifactNavigationTool() {
  const workbench = useWorkbenchContext();
  useFrontendTool({
    name: "fe_navigate_artifacts",
    description: "Open the Artifacts gallery or a specific artifact by stable slug. This tool only navigates; it never mutates artifact state.",
    parameters: Args,
    handler: async (value) => {
      const parsed = Args.safeParse(value);
      if (!parsed.success) return { success: false, error: "invalid artifact slug" };
      const path = artifactPath(parsed.data.slug);
      window.history.pushState({}, "", path);
      workbench.switchView("artifacts");
      return { success: true, path, slug: parsed.data.slug ?? null };
    },
  });
}
