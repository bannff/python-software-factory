/** Client-side mirror of the `CrewCreateInput` bounds so a bad form fails per field, before the round trip. */
export interface CrewFormValues {
  id: string; name: string; persona_id: string; project: string;
  memory_scope: string; model: string; description: string;
  workspace: string; triggers: string;
}

export type CrewFormErrors = Partial<Record<keyof CrewFormValues, string>>;

const SLUG = /^[a-z0-9][a-z0-9_-]{0,63}$/;
const SLUG_RULE = "Use lowercase letters, digits, hyphen or underscore (1–64), starting with a letter or digit.";
const MAX_TRIGGERS = 32;

export function validateCrewForm(form: CrewFormValues, creating: boolean): CrewFormErrors {
  const errors: CrewFormErrors = {};
  if (creating && !SLUG.test(form.id)) errors.id = form.id ? SLUG_RULE : "Enter a crew ID. " + SLUG_RULE;
  if (!form.name.trim()) errors.name = "Enter a name.";
  else if (form.name.length > 200) errors.name = "Name is limited to 200 characters.";
  if (!form.persona_id) errors.persona_id = "Pick a persona.";
  if (!form.project.trim()) errors.project = "Pick a project.";
  else if (form.project.length > 512) errors.project = "Project path is limited to 512 characters.";
  if (!SLUG.test(form.memory_scope)) {
    errors.memory_scope = form.memory_scope ? SLUG_RULE : "Enter a memory scope. " + SLUG_RULE;
  }
  if (form.description.length > 2000) errors.description = "Description is limited to 2000 characters.";
  const triggers = form.triggers.split(",").map((t) => t.trim()).filter(Boolean);
  if (triggers.length > MAX_TRIGGERS) errors.triggers = `At most ${MAX_TRIGGERS} triggers.`;
  else if (triggers.some((t) => t.length > 64)) errors.triggers = "Each trigger is limited to 64 characters.";
  return errors;
}
