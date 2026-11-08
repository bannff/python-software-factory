import { unwrapToolData } from "@/lib/tool-result-data";

function stringList(raw: unknown, key: "roots" | "projects"): string[] {
  const data = unwrapToolData(raw) as Record<string, unknown> | null;
  const list = data?.[key];
  if (!Array.isArray(list)) return [];
  return list.filter((item): item is string => typeof item === "string" && item.length > 0);
}

/** Parse the `devtools_list_allowed_project_roots` result into non-empty root paths. */
export function parseAllowedRoots(raw: unknown): string[] {
  return stringList(raw, "roots");
}

/** Parse the `devtools_list_projects` result into admissible project directories. */
export function parseProjects(raw: unknown): string[] {
  return stringList(raw, "projects");
}
