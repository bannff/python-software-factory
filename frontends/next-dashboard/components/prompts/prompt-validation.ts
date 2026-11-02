import type { PromptArg } from "./authored-prompts-api";

/** Client-side mirror of the agent prompt contract bounds, so a bad form fails per field. */
export interface PromptFormValues {
  prompt_id: string; description: string; template: string; args: PromptArg[];
}
export type PromptFormErrors = Partial<Record<"prompt_id" | "description" | "template" | "args" | "form", string>>;

const ID = /^[a-z][a-z0-9_-]{1,63}$/;
const ARG = /^[a-z][a-z0-9_]{0,31}$/;
/** The server's placeholder syntax: single braces, e.g. {finding}. */
const PLACEHOLDER = /\{([A-Za-z_][A-Za-z0-9_]*)\}/g;

/** Typed server refusals, keyed by the code `errorReason` surfaces. */
const SERVER_ERRORS: Readonly<Record<string, readonly [keyof PromptFormErrors, string]>> = {
  prompt_exists: ["prompt_id", "A prompt with this ID already exists."],
  prompt_revision_conflict: ["form", "This prompt changed elsewhere. Close the editor and reopen it to load the latest version."],
  prompt_not_found: ["form", "This prompt no longer exists."],
  prompt_invalid: ["form", "The server rejected this prompt. Check the fields and try again."],
};

export function serverFieldError(reason: string | undefined): PromptFormErrors | undefined {
  const code = reason === undefined ? undefined : Object.keys(SERVER_ERRORS).find((c) => reason.includes(c));
  return code ? { [SERVER_ERRORS[code][0]]: SERVER_ERRORS[code][1] } : undefined;
}

export function validatePromptForm(form: PromptFormValues, creating: boolean): PromptFormErrors {
  const errors: PromptFormErrors = {};
  if (creating && !ID.test(form.prompt_id)) {
    errors.prompt_id = "Use 2–64 lowercase letters, digits, hyphen or underscore, starting with a letter.";
  }
  if (form.description.length > 2000) errors.description = "Description is limited to 2000 characters.";
  if (!form.template.trim()) errors.template = "Enter the prompt template.";
  else if (form.template.length > 20_000) errors.template = "Template is limited to 20,000 characters.";
  else {
    const declared = new Set(form.args.map((a) => a.name));
    const unknown = [...new Set([...form.template.matchAll(PLACEHOLDER)].map((m) => m[1]))].filter((n) => !declared.has(n));
    if (unknown.length > 0) errors.template = `Declare an argument for ${unknown.map((n) => `{${n}}`).join(", ")}, or remove the placeholder.`;
  }
  if (form.args.length > 16) errors.args = "At most 16 arguments.";
  else if (form.args.some((a) => !ARG.test(a.name))) errors.args = "Argument names are lowercase letters, digits or underscore, starting with a letter.";
  else if (new Set(form.args.map((a) => a.name)).size !== form.args.length) errors.args = "Duplicate argument names.";
  return errors;
}
