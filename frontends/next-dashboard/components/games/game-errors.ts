import { errorReason, withReason } from "@/lib/error-reason";

/** Typed game refusals in words; anything else keeps the server's reason. */
const MESSAGES: Readonly<Record<string, string>> = {
  not_your_turn: "It's not your turn.",
  illegal_move: "That move isn't allowed.",
  game_not_found: "This game no longer exists.",
  unknown_game_type: "That game type isn't available.",
};

export function gameFailure(prose: string, cause: unknown): string {
  const reason = errorReason(cause);
  const code = reason === undefined ? undefined : Object.keys(MESSAGES).find((c) => reason.includes(c));
  return code ? MESSAGES[code] : withReason(prose, reason);
}
