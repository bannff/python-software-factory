"use client";

import { useCallback, useRef } from "react";
import { UseAgentUpdate, useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import type { SessionSummary } from "@/lib/hooks/use-session-list";
import { loadSessionHistory } from "@/lib/hooks/use-session-history";
import { useCrews } from "@/lib/hooks/use-crews";
import { startDefaultCrewSession } from "@/lib/start-default-crew-session";

export function useSessionRuntime(agentId: string) {
  const { agent } = useAgent({ agentId, updates: [UseAgentUpdate.OnMessagesChanged] });
  const { copilotkit } = useCopilotKit();
  const { defaultId } = useCrews();
  const revision = useRef(0);

  const setBinding = useCallback((session: SessionSummary) => {
    const current = (copilotkit?.properties ?? {}) as Record<string, unknown>;
    copilotkit?.setProperties({
      ...current,
      companion_x_agent_id: session.agent_id,
      companion_x_model: session.model,
      companion_x_memory_scope: session.memory_scope ?? "",
      companion_x_crew_id: session.crew_id ?? "",
    });
  }, [copilotkit]);

  const resumeSession = useCallback(async (session: SessionSummary) => {
    const requested = ++revision.current;
    const messages = await loadSessionHistory(session.session_id);
    if (requested !== revision.current) return false;
    agent.threadId = session.thread_id;
    agent.setMessages(messages);
    setBinding(session);
    return true;
  }, [agent, setBinding]);

  const createSession = useCallback(async () => {
    revision.current += 1;
    if (defaultId) {
      const { session } = await startDefaultCrewSession(defaultId);
      agent.threadId = session.thread_id;
      setBinding(session);
    } else {
      agent.threadId = crypto.randomUUID();
    }
    agent.setMessages([]);
  }, [agent, defaultId, setBinding]);

  return { agent, resumeSession, createSession };
}
