/**
 * JSON-schema → form-field derivation for the Cmd-K palette (bd:3jcls.4).
 *
 * Pure functions, no React, so they can be tested against schemas the repo
 * ACTUALLY ships rather than a hand-written fixture (see
 * `__tests__/schema-form.test.ts` + the Python drift guard
 * `test_catalog_fixture_matches_live_schemas.py`).
 *
 * Real FastMCP schemas are not the tidy textbook shape. A `str | None = None`
 * parameter arrives as `{anyOf: [{type: "string"}, {type: "null"}], default: null}`
 * with NO top-level `type` — so nullable unions have to be unwrapped or every
 * optional field renders as a raw JSON box. `cache_set.ttl_seconds` and
 * `telemetry_record_log.trace_id` are both that shape today.
 */

import type { JsonSchema } from "./tool-catalog";

export type FieldKind = "string" | "number" | "integer" | "boolean" | "enum" | "json";

export interface FormField {
  name: string;
  kind: FieldKind;
  required: boolean;
  /** Prefilled from the schema `default` when there is one. */
  defaultValue: unknown;
  options: string[];
  description: string;
  /** True when the parameter also accepts null (`T | None`). */
  nullable: boolean;
}

/** Strip the `null` arm off a nullable union and merge what is left. */
function unwrapNullable(schema: JsonSchema): { inner: JsonSchema; nullable: boolean } {
  if (!Array.isArray(schema.anyOf) || schema.anyOf.length === 0) {
    return { inner: schema, nullable: false };
  }
  const nonNull = schema.anyOf.filter((arm) => arm.type !== "null");
  const nullable = nonNull.length !== schema.anyOf.length;
  const inner = nonNull.length === 1 ? { ...nonNull[0] } : { ...schema, anyOf: nonNull };
  // `default` / `description` live on the OUTER node for optional params.
  if (schema.default !== undefined && inner.default === undefined) {
    inner.default = schema.default;
  }
  if (schema.description && !inner.description) inner.description = schema.description;
  return { inner, nullable };
}

function kindOf(schema: JsonSchema): FieldKind {
  if (Array.isArray(schema.enum) && schema.enum.length > 0) return "enum";
  switch (schema.type) {
    case "string": return "string";
    case "number": return "number";
    case "integer": return "integer";
    case "boolean": return "boolean";
    default: return "json"; // object / array / union → raw JSON textarea
  }
}

/** Derive the ordered field list for a tool's `input_schema`. */
export function deriveFields(schema: JsonSchema | undefined): FormField[] {
  const properties = schema?.properties ?? {};
  const required = new Set(schema?.required ?? []);
  return Object.entries(properties).map(([name, raw]) => {
    const { inner, nullable } = unwrapNullable(raw ?? {});
    return {
      name,
      kind: kindOf(inner),
      required: required.has(name),
      defaultValue: inner.default,
      options: (inner.enum ?? []).map(String),
      description: inner.description ?? "",
      nullable,
    };
  });
}

/** Initial form state: schema defaults prefilled, everything else blank. */
export function initialValues(fields: FormField[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const field of fields) {
    if (field.defaultValue === undefined || field.defaultValue === null) {
      out[field.name] = field.kind === "enum" ? (field.options[0] ?? "") : "";
      continue;
    }
    out[field.name] =
      typeof field.defaultValue === "object"
        ? JSON.stringify(field.defaultValue)
        : String(field.defaultValue);
  }
  return out;
}

/** Names of required fields the human has not filled in. */
export function missingRequired(
  fields: FormField[], values: Record<string, string>,
): string[] {
  return fields
    .filter((f) => f.required && String(values[f.name] ?? "").trim() === "")
    .map((f) => f.name);
}

function coerceOne(field: FormField, raw: string): unknown | undefined {
  const text = raw.trim();
  if (text === "") return undefined; // omit rather than send "" or null
  switch (field.kind) {
    case "number":
    case "integer": {
      const parsed = Number(text);
      return Number.isFinite(parsed) ? parsed : text;
    }
    case "boolean":
      return text === "true" || text === "1";
    case "json":
      try {
        return JSON.parse(text);
      } catch {
        return text;
      }
    default:
      return text;
  }
}

/**
 * Build the argument object that goes over the wire. Blank optional fields are
 * OMITTED so the server applies its own default instead of receiving `""`.
 */
export function coerceValues(
  fields: FormField[], values: Record<string, string>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const field of fields) {
    const coerced = coerceOne(field, values[field.name] ?? "");
    if (coerced !== undefined) out[field.name] = coerced;
  }
  return out;
}
