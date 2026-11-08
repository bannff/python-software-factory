"use client";

import { useCallback, useEffect, useState } from "react";
import { Gamepad2, Plus, RotateCcw, Trash2 } from "lucide-react";
import { ConfirmDelete } from "@/components/ui/confirm-delete";
import { EmptyState } from "@/components/ui/empty-state";
import { createGame, deleteGame, listGames, listGameTypes, moveInColumn, resetGame, type Game, type GameTypes } from "./games-api";
import { gameFailure } from "./game-errors";
import { GameBoard } from "./game-board";
import { useMutationRefresh } from "@/components/canvas/refresh-context";

/** Start, play, reset and delete games, driven by the games_* tools. */
export function GamesPanel() {
  const [games, setGames] = useState<Game[]>([]);
  const [types, setTypes] = useState<string[] | null>(null);
  const [catalog, setCatalog] = useState<GameTypes | null>(null);
  const [chosen, setChosen] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { version, notify } = useMutationRefresh();

  const refresh = useCallback(async () => {
    try { setGames(await listGames()); }
    catch (cause) { setNotice(gameFailure("Games are unavailable.", cause)); }
    finally { setLoaded(true); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh, version]);
  useEffect(() => { void listGameTypes().then(setCatalog).catch(() => undefined); }, []);
  const playable = (g: Game) => catalog?.humanPlayable == null || catalog.humanPlayable.includes(g.game_type);

  const run = async (action: () => Promise<void>, failure: string): Promise<boolean> => {
    setBusy(true); setNotice(null);
    try { await action(); await refresh(); notify(); return true; }
    catch (cause) { setNotice(gameFailure(failure, cause)); return false; }
    finally { setBusy(false); }
  };
  const openForm = async () => {
    try {
      const loaded = catalog ?? await listGameTypes();
      setCatalog(loaded);
      const available = loaded.humanPlayable ?? loaded.all;
      setTypes(available); setChosen(available[0] ?? "");
    } catch (cause) { setNotice(gameFailure("Game types are unavailable.", cause)); }
  };
  const start = async () => { if (await run(() => createGame(chosen), "Game could not be started.")) setTypes(null); };

  return (
    <section aria-label="Games" className="grid gap-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Games</h3>
        {types === null && <button type="button" aria-label="New game" onClick={() => void openForm()}
          className="inline-flex items-center gap-1.5 rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-accent/40">
          <Plus className="h-3.5 w-3.5" aria-hidden /> New game</button>}
      </div>
      {notice && <p role="alert" className="text-xs text-destructive">{notice}</p>}
      {types !== null && (
        <div className="flex items-center gap-2 rounded-xl border border-border/60 bg-card/20 p-3">
          <select aria-label="Game type" value={chosen} onChange={(e) => setChosen(e.target.value)}
            className="rounded-md border bg-background/50 px-3 py-2 text-sm">
            {types.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button type="button" disabled={busy || !chosen} onClick={() => void start()}
            className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">Start game</button>
          <button type="button" onClick={() => setTypes(null)} className="rounded-md border px-3 py-2 text-xs">Cancel</button>
        </div>
      )}
      {loaded && games.length === 0 && types === null && !notice && (
        <EmptyState icon={Gamepad2} title="No games yet" hint="Start one to play or let an agent play." />
      )}
      {games.filter(playable).map((g) => (
        <div key={g.game_id} className="grid gap-2 rounded-xl border border-border/60 bg-card/20 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-sm font-semibold">{g.game_id}</p>
              <p className="truncate text-xs text-muted-foreground">
                {[g.game_type, g.status, g.status === "active" ? `player ${g.current_player} to move` : g.winner ? `winner ${g.winner}` : ""].filter(Boolean).join(" · ")}
              </p>
            </div>
            <button type="button" aria-label={`Reset game ${g.game_id}`} disabled={busy}
              onClick={() => void run(() => resetGame(g.game_id), "Game could not be reset.")}
              className="rounded-md p-1.5 text-muted-foreground hover:text-foreground"><RotateCcw className="h-3.5 w-3.5" /></button>
            <ConfirmDelete label={`Delete game ${g.game_id}`} disabled={busy}
              onConfirm={() => void run(() => deleteGame(g.game_id), "Game could not be removed.")}
              className="rounded-md p-1.5 text-muted-foreground hover:text-destructive"><Trash2 className="h-3.5 w-3.5" /></ConfirmDelete>
          </div>
          {g.board.length > 0 && <GameBoard board={g.board} />}
          {g.moves.length > 0 && (
            <p className="truncate text-[11px] text-muted-foreground">
              {g.moves.slice(-8).map((m) => `P${m.player} → ${m.column + 1}`).join("  ·  ")}
            </p>
          )}
          {g.game_type === "connect_four" && g.status === "active" && (
            <div className="flex gap-1">
              {Array.from({ length: g.cols }, (_, c) => (
                <button key={c} type="button" aria-label={`Drop in column ${c + 1} for game ${g.game_id}`} disabled={busy}
                  onClick={() => void run(() => moveInColumn(g.game_id, g.current_player, c), "Move could not be played.")}
                  className="flex-1 rounded-md border border-border/50 py-1 text-[11px] text-muted-foreground hover:bg-accent/30 hover:text-foreground">{c + 1}</button>
              ))}
            </div>
          )}
        </div>
      ))}
      {games.some((g) => !playable(g)) && (
        <>
          <h3 className="mt-2 text-sm font-medium text-muted-foreground">Agent scenarios</h3>
          {games.filter((g) => !playable(g)).map((g) => (
            <div key={g.game_id} className="rounded-xl border border-border/40 bg-card/10 px-4 py-3">
              <p className="truncate font-mono text-sm">{g.game_id}</p>
              <p className="truncate text-xs text-muted-foreground">{[g.game_type, g.status].filter(Boolean).join(" · ")}</p>
            </div>
          ))}
        </>
      )}
    </section>
  );
}
