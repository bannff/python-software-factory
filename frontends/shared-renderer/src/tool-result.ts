/** Normalize gateway and typed MCP ToolResult envelopes before UI consumption. */
export function unwrapToolResult(raw: unknown, fallbackMessage = "Request failed"): unknown {
  let value = parseJson(raw);
  while (isRecord(value)) {
    const message = failureMessage(value, fallbackMessage);
    if (message) throw new Error(message);
    if ("result" in value) {
      value = parseJson(value.result);
      continue;
    }
    const structured = value.structured_content ?? value.structuredContent;
    if (structured !== undefined) {
      value = parseJson(structured);
      continue;
    }
    return "data" in value && value.data !== undefined ? value.data : value;
  }
  return value;
}

function failureMessage(value: Record<string, unknown>, fallback: string): string | null {
  const bareError = Object.keys(value).length === 1 && value.error != null;
  if (value.ok !== false && !bareError) return null;
  const error = value.error;
  if (isRecord(error) && typeof error.message === "string" && error.message) return error.message;
  return typeof error === "string" && error ? error : fallback;
}

function parseJson(value: unknown): unknown {
  if (typeof value !== "string") return value;
  try { return JSON.parse(value); } catch { return value; }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
