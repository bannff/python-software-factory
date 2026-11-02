import { useEffect } from "react";
import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";

const EVENT = "companion-x:send-prompt";

/** Ask the chat agent `text` as the user would. CopilotChat owns its composer
 * state and exposes no way to prefill it, so a one-click action sends. */
export function sendPrompt(text: string): void {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent<string>(EVENT, { detail: text }));
}

/** Chat host side of `sendPrompt`: adds the user message and runs the agent. */
export function useSendPromptHandler(agentId: string): void {
  const { agent } = useAgent({ agentId, updates: [] });
  const { copilotkit } = useCopilotKit();
  useEffect(() => {
    if (!agent) return;
    const onSend = (event: Event) => {
      agent.addMessage({ id: crypto.randomUUID(), role: "user", content: (event as CustomEvent<string>).detail });
      void copilotkit.runAgent({ agent });
    };
    window.addEventListener(EVENT, onSend);
    return () => window.removeEventListener(EVENT, onSend);
  }, [agent, copilotkit]);
}
