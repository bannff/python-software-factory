"use client";

/**
 * <DestructiveGuards /> — wires CopilotKit v2's `useHumanInTheLoop`
 * for the small set of MCP tools that mutate or destroy state
 * (bd-xpxa).
 *
 * Native pattern: the hook registers a frontend-tool whose render
 * component is auto-mounted inline in the chat stream when the agent
 * is about to fire one of these tools. CopilotKit pauses dispatch
 * until the user calls `respond({...})` from the render fn — so we
 * never need to wire bespoke approval middleware. The agent then
 * resumes (Approve) or aborts (Deny) via the standard tool-result
 * round-trip.
 *
 * The set of gated tools is intentionally small — the goal is
 * "destructive by default" not "exhaustive". Easy to extend later by
 * adding a new `useGuard()` line below.
 *
 * Out of scope here: non-destructive but expensive tools (long-running
 * scans, model invocations) — those should pivot to a cost-aware
 * confirm pattern, not a hard approval gate.
 */

import { useHumanInTheLoop } from "@copilotkit/react-core/v2";
import { z } from "zod";
import { ApprovalCard } from "@/components/chat/approval-card";

/* Tool argument schemas — kept loose (passthrough) so we never reject
 * a call the agent legitimately wants to make. The Zod schemas exist
 * mainly so the hook can decode the args for display; backend
 * validation is the source of truth. */

const SandboxExecuteArgs = z
  .object({
    command: z.string().optional(),
    container: z.string().optional(),
  })
  .passthrough();

const SandboxLifecycleArgs = z
  .object({ container: z.string().optional() })
  .passthrough();

const SecurityFindingArgs = z
  .object({
    finding_id: z.string().optional(),
    payload: z.unknown().optional(),
  })
  .passthrough();

const BlockchainTransferArgs = z
  .object({
    from: z.string().optional(),
    to: z.string().optional(),
    amount: z.union([z.string(), z.number()]).optional(),
  })
  .passthrough();

const BlockchainMintArgs = z
  .object({
    to: z.string().optional(),
    amount: z.union([z.string(), z.number()]).optional(),
  })
  .passthrough();

const MemoryDeleteArgs = z
  .object({
    memory_id: z.string().optional(),
    user_id: z.string().optional(),
  })
  .passthrough();

const EventsPublishArgs = z
  .object({
    topic: z.string().optional(),
    payload: z.unknown().optional(),
  })
  .passthrough();

interface GuardConfig<T extends z.ZodTypeAny> {
  name: string;
  description: string;
  parameters: T;
}

function useGuard<T extends z.ZodTypeAny>(cfg: GuardConfig<T>) {
  useHumanInTheLoop({
    name: cfg.name,
    description: cfg.description,
    parameters: cfg.parameters,
    render: ({ args, status, result, respond }) => (
      <ApprovalCard
        tool={cfg.name}
        args={args as Record<string, unknown> | undefined}
        status={status}
        result={result}
        onApprove={
          status === "executing" && respond
            ? () => respond({ approve: true })
            : undefined
        }
        onDeny={
          status === "executing" && respond
            ? () => respond({ approve: false })
            : undefined
        }
      />
    ),
  });
}

export function DestructiveGuards() {
  // Sandbox — anything that runs code or kills containers.
  useGuard({
    name: "sandbox.execute",
    description: "Run a command in a sandboxed container.",
    parameters: SandboxExecuteArgs,
  });
  useGuard({
    name: "sandbox.provision",
    description: "Provision a fresh sandbox container.",
    parameters: SandboxLifecycleArgs,
  });
  useGuard({
    name: "sandbox.terminate",
    description: "Terminate a sandbox container.",
    parameters: SandboxLifecycleArgs,
  });

  // Security findings — destructive writes / deletes.
  useGuard({
    name: "security_security.delete_finding",
    description: "Delete a security finding from the store.",
    parameters: SecurityFindingArgs,
  });
  useGuard({
    name: "security_security.persist_finding",
    description: "Persist a new security finding to the store.",
    parameters: SecurityFindingArgs,
  });

  // Blockchain — value-moving operations.
  useGuard({
    name: "blockchain_blockchain.transfer",
    description: "Transfer tokens between wallets.",
    parameters: BlockchainTransferArgs,
  });
  useGuard({
    name: "blockchain_blockchain.mint",
    description: "Mint new tokens.",
    parameters: BlockchainMintArgs,
  });

  // Memory — irreversible deletes.
  useGuard({
    name: "memory_memory_delete",
    description: "Delete a single memory entry.",
    parameters: MemoryDeleteArgs,
  });
  useGuard({
    name: "memory_memory_delete_user",
    description: "Delete every memory entry for a user.",
    parameters: MemoryDeleteArgs,
  });

  // Events — broadcast writes. Listed in the brief with a "investigate"
  // caveat: the events bus carries both observability pings and
  // domain-state writes. Treat publish as guard-worthy by default; the
  // agent rarely needs to publish on a user's behalf without consent.
  useGuard({
    name: "events_events_publish",
    description: "Publish an event to the platform event bus.",
    parameters: EventsPublishArgs,
  });

  return null;
}
