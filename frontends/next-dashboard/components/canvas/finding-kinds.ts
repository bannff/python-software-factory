import type { Finding } from "@/lib/types";

/** Distinct finding kinds with counts, most common first (ties keep first-seen order). */
export function kindCounts(findings: readonly Finding[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const f of findings) counts.set(f.type, (counts.get(f.type) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}
