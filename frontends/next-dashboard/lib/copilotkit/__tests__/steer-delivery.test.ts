import { describe, expect, it } from "vitest";
import type { Message } from "@ag-ui/core";
import {
  reconcileSteerDelivery, type SteeredMessage,
} from "../steer-delivery";

const messages = [{ id: "send-1", role: "user", content: "redirect" }] as Message[];
const delivery = {
  session_id: "session-1", delivery_id: "delivery-1", send_id: "send-1",
  state: "written", revision: 1,
};

describe("steer delivery reconciliation", () => {
  it("updates the existing optimistic user message by send_id", () => {
    const next = reconcileSteerDelivery(messages, delivery);
    expect(next).toHaveLength(1);
    expect((next[0] as SteeredMessage).steerDelivery).toEqual(delivery);
  });

  it("advances written to a terminal state without duplicating", () => {
    const written = reconcileSteerDelivery(messages, delivery);
    const consumed = reconcileSteerDelivery(written, {
      ...delivery, state: "consumed", revision: 2,
    });
    expect(consumed).toHaveLength(1);
    expect((consumed[0] as SteeredMessage).steerDelivery?.state).toBe("consumed");
  });

  it("ignores stale, malformed, unknown, and non-user targets", () => {
    const terminal = reconcileSteerDelivery(messages, {
      ...delivery, state: "requeued", revision: 2,
    });
    expect(reconcileSteerDelivery(terminal, delivery)).toBe(terminal);
    expect(reconcileSteerDelivery(messages, { ...delivery, state: "bogus" })).toBe(messages);
    expect(reconcileSteerDelivery(messages, { ...delivery, send_id: "missing" })).toBe(messages);
    const assistant = [{ ...messages[0], role: "assistant" }] as Message[];
    expect(reconcileSteerDelivery(assistant, delivery)).toBe(assistant);
  });
});
