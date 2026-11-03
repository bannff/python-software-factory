import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface Game {
  game_id: string; game_type: string; status: string; current_player: number; winner: number | null; cols: number;
  board: number[][]; moves: { player: number; column: number }[];
}

function gameFrom(raw: unknown): Game | null {
  const v = raw as Record<string, unknown> | null;
  if (!v || typeof v.game_id !== "string" || typeof v.game_type !== "string") return null;
  const cols = (v.config as { cols?: unknown } | undefined)?.cols;
  return { game_id: v.game_id, game_type: v.game_type, status: typeof v.status === "string" ? v.status : "",
    current_player: typeof v.current_player === "number" ? v.current_player : 0,
    winner: typeof v.winner === "number" ? v.winner : null, cols: typeof cols === "number" ? cols : 7,
    board: Array.isArray(v.board) ? v.board.filter(Array.isArray).map((row) => (row as unknown[]).map((c) => (typeof c === "number" ? c : 0))) : [],
    moves: Array.isArray(v.move_history) ? v.move_history.flatMap((m) => { const x = m as Record<string, unknown>; return typeof x?.player === "number" && typeof x?.column === "number" ? [{ player: x.player, column: x.column }] : []; }) : [] };
}

export async function listGames(): Promise<Game[]> {
  const data = unwrapToolData(await callTool("games_list")) as { games?: unknown };
  return Array.isArray(data?.games) ? data.games.map(gameFrom).filter((g): g is Game => g !== null) : [];
}
export async function listGameTypes(): Promise<string[]> {
  const data = unwrapToolData(await callTool("games_get_capabilities")) as { game_types?: unknown };
  return Array.isArray(data?.game_types) ? data.game_types.filter((t): t is string => typeof t === "string") : [];
}
export async function createGame(gameType: string): Promise<void> {
  unwrapToolData(await callTool("games_create", { game_type: gameType }));
}
export async function moveInColumn(gameId: string, player: number, column: number): Promise<void> {
  unwrapToolData(await callTool("games_move", { game_id: gameId, player, column }));
}
export async function resetGame(gameId: string): Promise<void> {
  unwrapToolData(await callTool("games_reset", { game_id: gameId }));
}
export async function deleteGame(gameId: string): Promise<void> {
  unwrapToolData(await callTool("games_delete", { game_id: gameId }));
}
