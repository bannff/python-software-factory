"use client";

import { useState } from "react";
import type { Wallet } from "./blockchain-api";

const FIELD = "w-full rounded-md border bg-background/50 px-3 py-2 text-sm";

/** Transfer or mint. Moving value takes two deliberate steps: review, then confirm. */
export function MoneyForm({ kind, wallets, busy, onSubmit, onCancel }: {
  kind: "transfer" | "mint"; wallets: Wallet[]; busy: boolean;
  onSubmit: (from: string, to: string, amount: number) => void; onCancel: () => void;
}) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [amount, setAmount] = useState("");
  const [armed, setArmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const value = Number(amount);
  const options = (
    <>{[<option key="" value="">Choose…</option>, ...wallets.map((w) => <option key={w.wallet_id} value={w.wallet_id}>{w.wallet_id}</option>)]}</>
  );
  const review = () => {
    if (kind === "transfer" && !from) return setError("Choose the wallet to send from.");
    if (!to) return setError(kind === "mint" ? "Choose the wallet to mint to." : "Choose the wallet to send to.");
    if (!(value > 0)) return setError("Enter an amount above zero.");
    if (kind === "transfer" && from === to) return setError("Pick two different wallets.");
    setError(null); setArmed(true);
  };
  const summary = kind === "transfer" ? `transfer of ${value} from ${from} to ${to}` : `mint of ${value} to ${to}`;

  return (
    <div className="grid gap-3 rounded-xl border border-border/60 bg-card/20 p-4">
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      {kind === "transfer" && <label className="grid gap-1 text-xs"><span>From wallet</span>
        <select aria-label="From wallet" className={FIELD} value={from} disabled={armed} onChange={(e) => setFrom(e.target.value)}>{options}</select></label>}
      <label className="grid gap-1 text-xs"><span>To wallet</span>
        <select aria-label="To wallet" className={FIELD} value={to} disabled={armed} onChange={(e) => setTo(e.target.value)}>{options}</select></label>
      <label className="grid gap-1 text-xs"><span>Amount</span>
        <input aria-label="Amount" type="number" min="0" className={FIELD} value={amount} disabled={armed} onChange={(e) => setAmount(e.target.value)} /></label>
      <div className="flex items-center gap-2">
        {armed ? (
          <button type="button" disabled={busy} aria-label={`Confirm ${summary}`} onClick={() => onSubmit(from, to, value)}
            className="rounded-md bg-destructive px-3 py-2 text-xs text-destructive-foreground disabled:opacity-40">Confirm {summary}</button>
        ) : (
          <button type="button" aria-label={`Review ${kind}`} onClick={review} className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white">Review {kind}</button>
        )}
        <button type="button" onClick={armed ? () => setArmed(false) : onCancel} className="rounded-md border px-3 py-2 text-xs">{armed ? "Back" : "Cancel"}</button>
      </div>
    </div>
  );
}
