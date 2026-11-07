import { toast } from "sonner";

interface CopilotErrorEvent { error: Error; code: string; context: Record<string, unknown> }

const NO_MODEL = "No chat model is set up on this server yet. Ask an operator to configure one, then try again.";

/** Plain-words notice for run errors we can explain; null leaves the default handling alone. */
export function chatRunErrorNotice(event: CopilotErrorEvent): string | null {
  if (event.context?.runtimeErrorCode === "model_not_configured") return NO_MODEL;
  // The streaming path sends the message without a code.
  if (/no chat model configured/i.test(event.error?.message ?? "")) return NO_MODEL;
  return null;
}

export function handleCopilotError(event: CopilotErrorEvent): void {
  const notice = chatRunErrorNotice(event);
  if (notice) toast.error(notice, { id: "chat-model-not-configured", duration: 10000 });
}
