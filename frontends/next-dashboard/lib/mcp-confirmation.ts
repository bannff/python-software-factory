export type ConfirmationDecision = "accept" | "decline" | "cancel";

export interface ConfirmationRequest {
  id: number;
  message: string;
  field: string;
}

type Pending = ConfirmationRequest & {
  resolve: (decision: ConfirmationDecision) => void;
  timer: ReturnType<typeof setTimeout>;
};

type Listener = () => void;

const listeners = new Set<Listener>();
const queue: Pending[] = [];
let current: Pending | null = null;
let sequence = 0;

function notify() {
  for (const listener of listeners) listener();
}

function advance() {
  current = queue.shift() ?? null;
  notify();
}

function settle(id: number, decision: ConfirmationDecision) {
  if (current?.id === id) {
    const pending = current;
    current = null;
    clearTimeout(pending.timer);
    pending.resolve(decision);
    advance();
    return;
  }
  const index = queue.findIndex((item) => item.id === id);
  if (index < 0) return;
  const [pending] = queue.splice(index, 1);
  clearTimeout(pending.timer);
  pending.resolve(decision);
}

/** Queue one MCP confirmation. Unanswered prompts cancel after two minutes. */
export function requestConfirmation(
  message: string,
  field: string,
): Promise<ConfirmationDecision> {
  return new Promise((resolve) => {
    const id = ++sequence;
    const pending: Pending = {
      id,
      message,
      field,
      resolve,
      timer: setTimeout(() => settle(id, "cancel"), 120_000),
    };
    if (current) queue.push(pending);
    else {
      current = pending;
      notify();
    }
  });
}

export function resolveConfirmation(decision: ConfirmationDecision) {
  if (current) settle(current.id, decision);
}

export function cancelAllConfirmations() {
  const pending = current ? [current, ...queue] : [...queue];
  current = null;
  queue.length = 0;
  for (const item of pending) {
    clearTimeout(item.timer);
    item.resolve("cancel");
  }
  notify();
}

export function subscribeConfirmations(listener: Listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getConfirmationSnapshot(): ConfirmationRequest | null {
  return current;
}
