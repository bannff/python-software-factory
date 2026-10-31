import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

/**
 * React's own bundles are the only modules that assign a `version` field next
 * to a renderer (`react` / `react-dom` production builds ship
 * `version="18.3.1"`, and Next's compiled React ships its canary version the
 * same way). Classifiers such as `react-is` carry no version marker, which is
 * what makes this a renderer probe rather than a generic string search.
 */
const REACT_VERSION_MARKER = /\bversion\s*[:=]\s*["'](\d+\.\d+\.\d+[^"']*)["']/g;

function collectJsFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return collectJsFiles(full);
    return entry.name.endsWith(".js") ? [full] : [];
  });
}

/**
 * Distinct React runtime versions bundled under `root`, i.e. the versions of
 * the React renderers whose code was emitted into the built output. Only
 * React-major markers (18.x / 19.x) are returned so unrelated `version` fields
 * (e.g. Next's own `16.3.5`) cannot masquerade as a React copy.
 */
export function scanBundledReactVersions(root: string): string[] {
  const versions = new Set<string>();
  for (const file of collectJsFiles(root)) {
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(REACT_VERSION_MARKER)) versions.add(match[1]);
  }
  return [...versions].filter((v) => v.startsWith("18.") || v.startsWith("19."));
}
