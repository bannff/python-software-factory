import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

/**
 * Single source of truth for every Agent authoring affordance in the
 * dashboard (`agent_authoring_capabilities`).
 *
 * The probe answers from the SAME `AuthoringPolicy` the server gates use
 * (denied tools are absent from `tools/list` and the probe booleans are
 * false), so an affordance and its enabling flag can never disagree.
 */
export interface AuthoringRoot { path: string; source: "env" | "default" }

export interface LifecycleSurface {
  add: boolean; create: boolean; update: boolean; delete: boolean; fork: boolean; reset: boolean;
}

export interface ConfigSurface { read: boolean; write: boolean }

export interface AuthoringCapabilities {
  config: ConfigSurface;
  skills: LifecycleSurface;
  steering: LifecycleSurface;
  agent_templates: LifecycleSurface;
  roots: { config: AuthoringRoot; skills: AuthoringRoot; steering: AuthoringRoot };
}

/** Env variable that opens each surface (server: authoring/policy.py). */
export const AUTHORING_SURFACE_VARIABLE = {
  config: "FACTORY_AGENT_AUTHORING_CONFIG",
  skills: "FACTORY_AGENT_AUTHORING_SKILLS",
  steering: "FACTORY_AGENT_AUTHORING_STEERING",
  agent_templates: "FACTORY_AGENT_AUTHORING_AGENT_TEMPLATES",
} as const;
export type AuthoringSurface = keyof typeof AUTHORING_SURFACE_VARIABLE;

const SURFACE_ROOT: Record<AuthoringSurface, keyof AuthoringCapabilities["roots"]> = {
  config: "config", skills: "skills", steering: "steering", agent_templates: "config",
};

const LIFECYCLE = ["add", "create", "update", "delete", "fork", "reset"] as const;

function asRecord(raw: unknown): Record<string, unknown> {
  return raw && typeof raw === "object" ? raw as Record<string, unknown> : {};
}

function lifecycle(raw: unknown): LifecycleSurface {
  const value = asRecord(raw);
  return Object.fromEntries(LIFECYCLE.map((action) => [action, value[action] === true])) as unknown as LifecycleSurface;
}

function root(raw: unknown): AuthoringRoot {
  const value = asRecord(raw);
  return {
    path: typeof value.path === "string" ? value.path : "",
    source: value.source === "env" ? "env" : "default",
  };
}

function normalize(raw: unknown): AuthoringCapabilities {
  const value = asRecord(raw);
  const config = asRecord(value.config);
  const roots = asRecord(value.roots);
  return {
    config: { read: config.read === true, write: config.write === true },
    skills: lifecycle(value.skills),
    steering: lifecycle(value.steering),
    agent_templates: lifecycle(value.agent_templates),
    roots: { config: root(roots.config), skills: root(roots.skills), steering: root(roots.steering) },
  };
}

let capabilitiesPromise: Promise<AuthoringCapabilities> | null = null;

/** Fetch (and memoize) the deployment's per-action authoring capability. */
export function getAuthoringCapabilities(): Promise<AuthoringCapabilities> {
  if (!capabilitiesPromise) {
    capabilitiesPromise = (async () =>
      normalize(unwrapToolData(await callTool("agent_authoring_capabilities"))))()
      .catch((error) => {
        capabilitiesPromise = null; // a failed probe must stay retryable
        throw error;
      });
  }
  return capabilitiesPromise;
}

/** Drop the memoized probe (test hatch; also after an operator policy change). */
export function resetAuthoringCapabilities(): void {
  capabilitiesPromise = null;
}

/** Reason text for a disabled affordance: names the variable AND the write root. */
export function authoringGateNotice(
  capabilities: AuthoringCapabilities, surface: AuthoringSurface, action: string,
): string {
  const variable = AUTHORING_SURFACE_VARIABLE[surface];
  const root = capabilities.roots[SURFACE_ROOT[surface]];
  return `Disabled by the Agent authoring gate: set ${variable}=${action} `
    + `(comma-separated; 'all' opens ${surface}) to enable it. Writes go to ${root.path}.`;
}
