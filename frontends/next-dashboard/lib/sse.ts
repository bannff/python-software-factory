import type { AGUIEvent, ChatMessage, RunAgentInput } from "./types";

/**
 * AG-UI SSE stream parser.
 *
 * POSTs to /ag-ui/run with a RunAgentInput body and yields typed
 * AG-UI events as they arrive over the SSE connection.
 */

export class SSEError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "SSEError";
  }
}

/**
 * Stream AG-UI events from the backend.
 *
 * @param messages - Chat message history to send
 * @param threadId - Conversation thread ID (auto-generated if omitted)
 * @param state    - Optional shared state object
 * @param signal   - Optional AbortSignal for cancellation
 */
export async function* streamAGUI(
  messages: ChatMessage[],
  threadId?: string,
  state?: Record<string, unknown>,
  signal?: AbortSignal,
): AsyncGenerator<AGUIEvent> {
  const body: RunAgentInput = {
    messages,
    ...(threadId && { threadId }),
    ...(state && { state }),
  };

  const response = await fetch("/ag-ui/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new SSEError(response.status, text);
  }

  if (!response.body) {
    throw new SSEError(0, "Response body is null — SSE not supported");
  }

  yield* parseSSEStream(response.body);
}

/**
 * Parse a ReadableStream of SSE bytes into typed AG-UI events.
 *
 * Handles chunked delivery — SSE data lines may be split across
 * multiple chunks, so we buffer partial lines until we see a newline.
 */
async function* parseSSEStream(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<AGUIEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by double newlines
      const parts = buffer.split("\n\n");
      // Last element is either empty or an incomplete chunk
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        const event = parseSSEEvent(part);
        if (event) yield event;
      }
    }

    // Flush any remaining buffered data
    if (buffer.trim()) {
      const event = parseSSEEvent(buffer);
      if (event) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Parse a single SSE event block into a typed AG-UI event.
 *
 * Supports multi-line `data:` fields (concatenated with newlines per spec).
 * Ignores `event:`, `id:`, and `retry:` fields — the backend only sends `data:`.
 */
function parseSSEEvent(raw: string): AGUIEvent | null {
  const lines = raw.split("\n");
  let data = "";

  for (const line of lines) {
    if (line.startsWith("data: ")) {
      data += (data ? "\n" : "") + line.slice(6);
    } else if (line.startsWith("data:")) {
      data += (data ? "\n" : "") + line.slice(5);
    }
    // Skip comment lines (starting with :) and other fields
  }

  if (!data) return null;

  try {
    return JSON.parse(data) as AGUIEvent;
  } catch {
    // Malformed JSON — skip this event
    return null;
  }
}
