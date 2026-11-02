import { unwrapToolData } from "@/lib/tool-result-data";

/** Parse the `devtools_list_allowed_project_roots` result into non-empty root paths. */
export function parseAllowedRoots(raw: unknown): string[] {
  const data = unwrapToolData(raw) as { roots?: unknown };
  if (!data || !Array.isArray(data.roots)) return [];
  return data.roots.filter((root): root is string => typeof root === "string" && root.length > 0);
}
