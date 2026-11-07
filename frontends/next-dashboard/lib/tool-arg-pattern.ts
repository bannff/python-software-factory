import { fetchToolCatalog } from "@/lib/tool-catalog";

/** The pattern a tool publishes for one input argument, so forms never carry
 * their own copy of a backend rule. Null when the catalog does not state one. */
export async function toolArgPattern(tool: string, arg: string): Promise<string | null> {
  const { tools } = await fetchToolCatalog();
  const pattern = tools.find((entry) => entry.qualified_name === tool)?.input_schema?.properties?.[arg]?.pattern;
  return typeof pattern === "string" ? pattern : null;
}
