import { useEffect } from "react";
import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";

const EVENT = "companion-x:send-prompt";
const PENDING_KEY = "companion-x:pending-prompt";
const CHAT_ROUTE = "/";

function queue(text: string): void {
  try { sessionStorage.setItem(PENDING_KEY, text); } catch { /* storage blocked: the prompt is dropped, the chat still opens */ }
}

function takeQueued(): string | null {
  try {
    const text = sessionStorage.getItem(PENDING_KEY);
    if (text !== null) sessionStorage.removeItem(PENDING_KEY);
    return text;
  } catch { return null; }
}

/** Ask the chat agent `text` as the user would. CopilotChat owns its composer
 * state and exposes no way to prefill it, so a one-click action sends. When no
 * chat is mounted (e.g. a /views/<id> page) the prompt is queued and the chat
 * opens, where it is sent on arrival, rather than silently doing nothing. */
export function sendPrompt(text: string): void {
  if (typeof window === "undefined") return;
  const handled = !window.dispatchEvent(new CustomEvent<string>(EVENT, { detail: text, cancelable: true }));
  if (handled) return;
  queue(text);
  window.location.assign(CHAT_ROUTE);
}

/** Chat host side of `sendPrompt`: adds the user message and runs the agent. */
export function useSendPromptHandler(agentId: string): void {
  const { agent } = useAgent({ agentId, updates: [] });
  const { copilotkit } = useCopilotKit();
  useEffect(() => {
    if (!agent) return;
    const send = (text: string) => {
      agent.addMessage({ id: crypto.randomUUID(), role: "user", content: text });
      void copilotkit.runAgent({ agent });
    };
    const onSend = (event: Event) => {
      event.preventDefault(); // tells sendPrompt a chat took it
      send((event as CustomEvent<string>).detail);
    };
    window.addEventListener(EVENT, onSend);
    const queued = takeQueued();
    if (queued !== null) send(queued);
    return () => window.removeEventListener(EVENT, onSend);
  }, [agent, copilotkit]);
}
