/**
 * Single source of truth for the Crews-form field explanations (issue #140).
 * Every hint is grounded in the crew contract/runtime — see the evidence
 * table on #140 — so the copy cannot drift per field. `crew-editor.tsx`
 * renders these through the shared `<Field>` helper; do not inline copy.
 */

/** Form-level explanation shown next to the editor title. */
export const CREW_FORM_HINT =
  "A crew is a frozen, owner-scoped definition persisted as typed data — not a runtime. " +
  "It bundles a persona, project, workspace, memory scope, an inheritable model, and " +
  "discovery triggers, and is applied to every session that runs under it.";

export interface CrewFieldHint {
  /** Visible label, also used for the affordance's aria-label. */
  label: string;
  /** What the field is, why it is asked for, its limits, and empty-value behavior. */
  hint: string;
}

export const CREW_FIELD_HINTS = {
  id: {
    label: "Crew ID",
    hint:
      "Immutable identifier, set only at create and never editable afterwards. " +
      "Lowercase letters, digits, hyphen and underscore only, 1–64 characters, " +
      "starting with a letter or digit (^[a-z0-9][a-z0-9_-]{0,63}$).",
  },
  name: {
    label: "Name",
    hint:
      "Human-readable label shown in the crews list. Required; 1–200 characters.",
  },
  persona_id: {
    label: "Persona",
    hint:
      "The registered agent persona this crew runs as. The picker lists every " +
      "persona in the registry; the persona supplies the default model when Model " +
      "is left to inherit.",
  },
  model: {
    label: "Model",
    hint:
      "Empty means inherit: the effective model is the persona's model unless the " +
      "session or crew overrides it — resolved as " +
      "models.effective_id(request.model_id, persona.model). Pick a value to pin " +
      "the crew to one model.",
  },
  project: {
    label: "Project path",
    hint:
      "Absolute path of the project that a crew-spawned session binds to. Every " +
      "session must carry a project — without one, devtools calls fail with " +
      "tool_execution_failed. Required; 1–512 characters.",
  },
  memory_scope: {
    label: "Memory scope",
    hint:
      "Selects which memory the agent reads and writes for this crew's sessions — " +
      "it scopes what the agent remembers. Lowercase letters, digits, hyphen and " +
      "underscore, 1–64 characters (^[a-z0-9][a-z0-9_-]{0,63}$). Sessions with no " +
      'scope fall back to "default".',
  },
  description: {
    label: "Description",
    hint:
      "Free-text summary of what the crew is for. Optional; up to 2000 characters.",
  },
  triggers: {
    label: "Triggers (comma-separated)",
    hint:
      "Comma-separated discovery metadata describing what the crew is for " +
      "(up to 32 entries, each ≤64 characters). Stored on the crew definition and " +
      "exposed to clients; no agent runtime consumes them yet, so they do not " +
      "trigger any behavior today.",
  },
} as const satisfies Record<string, CrewFieldHint>;

export type CrewFieldKey = keyof typeof CREW_FIELD_HINTS;
