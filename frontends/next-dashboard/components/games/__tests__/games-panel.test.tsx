import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { GamesPanel } from "../games-panel";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
const emptyBoard = () => Array.from({ length: 6 }, () => Array(7).fill(0));
const game = (id: string, status = "active", board = emptyBoard(), moves: unknown[] = []) => ({ game_id: id, game_type: "connect_four", status, current_player: 1, winner: null, board, move_history: moves, config: { rows: 6, cols: 7 } });
let games: unknown[] = [];
const typed = (code: string) => Object.assign(new Error(code), { reason: code });

beforeEach(() => {
  callTool.mockReset(); games = [];
  callTool.mockImplementation(async (name: string) => {
    if (name === "games_list") return ok({ games, count: games.length });
    if (name === "games_get_capabilities") return ok({ game_types: ["connect_four", "finding_triage"] });
    if (name === "games_delete") return ok({ game_id: "g1", deleted: true });
    return ok(game("g-new"));
  });
});

describe("GamesPanel", () => {
  it("offers a first game when there are none", async () => {
    render(<GamesPanel />);
    expect(await screen.findByText("No games yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "New game" })).toBeTruthy();
  });

  it("creates a game of the chosen type", async () => {
    render(<GamesPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "New game" }));
    await screen.findByRole("option", { name: "finding_triage" });
    fireEvent.change(screen.getByLabelText("Game type"), { target: { value: "finding_triage" } });
    fireEvent.click(screen.getByRole("button", { name: "Start game" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("games_create", { game_type: "finding_triage" }));
  });

  it("lists games and resets or deletes one after confirmation", async () => {
    games = [game("g1"), game("g2", "finished")];
    render(<GamesPanel />);
    expect(await screen.findByText("g1")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Reset game g1" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("games_reset", { game_id: "g1" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete game g1" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete game g1" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("games_delete", { game_id: "g1" }));
  });

  it("plays a connect-four column for the current player", async () => {
    games = [game("g1")];
    render(<GamesPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Drop in column 4 for game g1" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("games_move", { game_id: "g1", player: 1, column: 3 }));
  });

  it("shows a typed refusal in words", async () => {
    games = [game("g1")];
    callTool.mockImplementation(async (name: string) => {
      if (name === "games_list") return ok({ games, count: 1 });
      if (name === "games_get_capabilities") return ok({ game_types: ["connect_four"] });
      throw typed("not_your_turn");
    });
    render(<GamesPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Drop in column 1 for game g1" }));
    expect(await screen.findByText(/not your turn/i)).toBeTruthy();
  });

  it("draws the board with each player's pieces where they landed", async () => {
    const board = emptyBoard();
    board[5][3] = 1; board[5][4] = 2; board[4][3] = 1;
    games = [game("g1", "active", board)];
    render(<GamesPanel />);
    await screen.findByText("g1");
    expect(screen.getAllByRole("img", { name: /^Column \d, row \d: /i })).toHaveLength(42);
    expect(screen.getAllByRole("img", { name: /player 1$/i })).toHaveLength(2);
    expect(screen.getAllByRole("img", { name: /player 2$/i })).toHaveLength(1);
  });

  it("lists the moves played so far", async () => {
    const board = emptyBoard(); board[5][3] = 1; board[5][4] = 2;
    games = [game("g1", "active", board, [{ player: 1, column: 3, row: 5 }, { player: 2, column: 4, row: 5 }])];
    render(<GamesPanel />);
    expect(await screen.findByText(/P1 → 4/)).toBeTruthy();
    expect(screen.getByText(/P2 → 5/)).toBeTruthy();
  });

  it("shows no board for the 1x1 placeholder the security games return", async () => {
    games = [{ ...game("g3"), game_type: "ctf_challenge", board: [[0]] }];
    render(<GamesPanel />);
    await screen.findByText("g3");
    expect(screen.queryAllByRole("img", { name: /^Column/i })).toHaveLength(0);
  });

  it("shows no board for a game type without one", async () => {
    games = [{ ...game("g2"), game_type: "ctf_challenge", board: [] }];
    render(<GamesPanel />);
    await screen.findByText("g2");
    expect(screen.queryAllByRole("img", { name: /^Column/i })).toHaveLength(0);
  });
});
