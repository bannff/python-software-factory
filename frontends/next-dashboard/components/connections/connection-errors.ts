import { errorReason, withReason } from "@/lib/error-reason";

/** Typed `connections_*` refusals in words; anything else keeps the server's reason. */
const MESSAGES: Readonly<Record<string, string>> = {
  connections_document_invalid: "That isn’t a valid mcpServers JSON document.",
  connections_revision_conflict: "This server changed elsewhere. Refresh and try again.",
  connections_invalid: "The server settings were rejected.",
  connections_identity_required: "Sign in to manage external servers.",
};

export function connectionFailure(prose: string, cause: unknown): string {
  const reason = errorReason(cause);
  const message = reason === undefined ? undefined : MESSAGES[reason];
  return message ? `${prose} ${message}` : withReason(prose, reason);
}
