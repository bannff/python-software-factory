import { cn } from "@/lib/utils";

const PIECE = ["bg-muted/30", "bg-violet-500", "bg-amber-400"];

/** A drop-board: one dot per cell, coloured by who holds it. Cell 0 is empty. */
export function GameBoard({ board }: { board: number[][] }) {
  const cols = board[0]?.length ?? 0;
  // The security games return a 1x1 placeholder; a one-cell "board" is not a board.
  if (cols < 2 || board.length < 2) return null;
  return (
    <div className="grid gap-1 rounded-lg border border-border/40 bg-card/30 p-2" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
      {board.map((row, r) => row.map((cell, c) => (
        <span key={`${r}-${c}`} role="img" aria-label={`Column ${c + 1}, row ${r + 1}: ${cell === 0 ? "empty" : `player ${cell}`}`}
          className={cn("mx-auto h-4 w-4 rounded-full", PIECE[cell] ?? PIECE[0])} />
      )))}
    </div>
  );
}
