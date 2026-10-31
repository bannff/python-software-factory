"use client";

import { useEffect } from "react";
import type { Message } from "@ag-ui/core";
import type { AgentSubscriber } from "@ag-ui/client";
import { useAgent } from "@copilotkit/react-core/v2";

export type SteerDeliveryState = "written" | "consumed" | "requeued";
export interface SteerDelivery {
  session_id: string;
  delivery_id: string;
  send_id: string;
  state: SteerDeliveryState;
  revision: number;
}
export type SteeredMessage = Message & { steerDelivery?: SteerDelivery };

export function parseSteerDelivery(value: unknown): SteerDelivery | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  if (!["written", "consumed", "requeued"].includes(String(item.state))) return null;
  if (!["session_id", "delivery_id", "send_id"].every(
    (key) => typeof item[key] === "string" && item[key] !== "",
  )) return null;
  if (!Number.isInteger(item.revision) || Number(item.revision) < 1) return null;
  return item as unknown as SteerDelivery;
}

export function reconcileSteerDelivery(
  messages: Message[], value: unknown,
): Message[] {
  const delivery = parseSteerDelivery(value);
  if (!delivery) return messages;
  const index = messages.findIndex(
    (message) => message.role === "user" && message.id === delivery.send_id,
  );
  if (index < 0) return messages;
  const current = messages[index] as SteeredMessage;
  const currentRevision = current.steerDelivery?.revision;
  if (currentRevision !== undefined && currentRevision > delivery.revision) return messages;
  const next = [...messages];
  next[index] = { ...current, steerDelivery: delivery } as unknown as Message;
  return next;
}

export function SteerDeliveryListener({ agentId }: { agentId: string }) {
  const { agent } = useAgent({ agentId });
  useEffect(() => {
    if (!agent) return;
    const subscriber: AgentSubscriber = {
      onCustomEvent: ({ event }) => {
        if (event.name !== "session.steer") return;
        const next = reconcileSteerDelivery(agent.messages, event.value);
        if (next !== agent.messages) agent.setMessages(next);
      },
    };
    const subscription = agent.subscribe(subscriber);
    return () => subscription.unsubscribe();
  }, [agent]);
  return null;
}
