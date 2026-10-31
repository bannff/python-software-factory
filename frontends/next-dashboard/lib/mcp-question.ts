export type QuestionDecision =
  | { action: "answer"; value: string }
  | { action: "cancel" };

export interface QuestionRequest {
  id: number;
  message: string;
  field: string;
  options: string[];
}

type Pending = QuestionRequest & {
  resolve: (decision: QuestionDecision) => void;
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

function settle(id: number, decision: QuestionDecision) {
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

/** Queue one MCP multiple-choice question. Unanswered prompts cancel after two minutes. */
export function requestQuestion(
  message: string,
  field: string,
  options: string[],
): Promise<QuestionDecision> {
  return new Promise((resolve) => {
    const id = ++sequence;
    const pending: Pending = {
      id,
      message,
      field,
      options,
      resolve,
      timer: setTimeout(() => settle(id, { action: "cancel" }), 120_000),
    };
    if (current) queue.push(pending);
    else {
      current = pending;
      notify();
    }
  });
}

export function answerQuestion(value: string) {
  if (current) settle(current.id, { action: "answer", value });
}

export function cancelQuestion() {
  if (current) settle(current.id, { action: "cancel" });
}

export function cancelAllQuestions() {
  const pending = current ? [current, ...queue] : [...queue];
  current = null;
  queue.length = 0;
  for (const item of pending) {
    clearTimeout(item.timer);
    item.resolve({ action: "cancel" });
  }
  notify();
}

export function subscribeQuestions(listener: Listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getQuestionSnapshot(): QuestionRequest | null {
  return current;
}
