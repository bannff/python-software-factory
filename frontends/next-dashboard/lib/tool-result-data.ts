type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null;
}

function parseJson(value: unknown): unknown {
  if (typeof value !== "string") return value;
  try { return JSON.parse(value); } catch { return value; }
}

function failureMessage(value: UnknownRecord): string {
  const error = value.error;
  if (isRecord(error) && typeof error.message === "string") return error.message;
  if (typeof error === "string" && error) return error;
  return "Tool request failed";
}

/** Unwrap transport/ToolResult layers while preserving domain-level `result`. */
export function unwrapToolData(raw: unknown): unknown {
  let value = parseJson(raw);
  if (isRecord(value) && "tool" in value && "result" in value) {
    value = parseJson(value.result);
  }
  if (isRecord(value)) {
    const structured = value.structured_content ?? value.structuredContent;
    if (structured !== undefined) value = parseJson(structured);
  }
  if (isRecord(value) && ("schema_version" in value || "ok" in value)) {
    if (value.ok === false) throw new Error(failureMessage(value));
    if ("data" in value) return parseJson(value.data);
  }
  return value;
}
