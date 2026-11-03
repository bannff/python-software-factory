import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { GamesPanel } from "../games-panel";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
const game = (id: string, status = "active") => ({ game_id: id, game_type: "connect_four", status, current_player: 1, winner: null, move_history: [] });
let games: unknown[] = [];
const typed = (code: string) => Object.assign(new Error(code), { reason: code });

beforeEach(() => {
  callTool.mockReset(); games = [];
  callTool.mockImplementation(async (name: string) => {
    if (name === "games_list") return ok({ games, count: games.length });
    if (name === "get_capabilities") return ok({ game_types: ["connect_four", "finding_triage"] });
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
      if (name === "get_capabilities") return ok({ game_types: ["connect_four"] });
      throw typed("not_your_turn");
    });
    render(<GamesPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Drop in column 1 for game g1" }));
    expect(await screen.findByText(/not your turn/i)).toBeTruthy();
  });
});
