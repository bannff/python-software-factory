"use client";

import { useCallback, useEffect, useState } from "react";
import { Coins, Plus, ShieldCheck } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { errorReason, withReason } from "@/lib/error-reason";
import { createWallet, ledgerFailure, listWallets, mint, transfer, verifyChain, type ChainCheck, type Wallet } from "./blockchain-api";
import { MoneyForm } from "./money-form";
import { useMutationRefresh } from "@/components/canvas/refresh-context";

type Mode = "wallet" | "transfer" | "mint" | null;
const BTN = "inline-flex items-center gap-1.5 rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-accent/40";
const FIELD = "w-full rounded-md border bg-background/50 px-3 py-2 text-sm";

/** Wallets, value movement and a chain check, driven by the blockchain_* tools. */
export function BlockchainPanel() {
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [mode, setMode] = useState<Mode>(null);
  const [owner, setOwner] = useState("");
  const [start, setStart] = useState("0");
  const [check, setCheck] = useState<ChainCheck | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { version, notify } = useMutationRefresh();

  const refresh = useCallback(async () => {
    try { setWallets(await listWallets()); }
    catch (cause) { setNotice(withReason("Wallets are unavailable.", errorReason(cause))); }
    finally { setLoaded(true); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh, version]);

  const run = async (action: () => Promise<void>, failure: string) => {
    setBusy(true); setNotice(null);
    try { await action(); setMode(null); await refresh(); notify(); }
    catch (cause) { setNotice(ledgerFailure(failure, cause)); }
    finally { setBusy(false); }
  };
  const open = (next: Mode) => { setNotice(null); setMode(next); };

  return (
    <section aria-label="Blockchain controls" className="grid gap-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Wallets</h3>
        {mode === null && (
          <div className="flex flex-wrap gap-2">
            <button type="button" aria-label="New wallet" className={BTN} onClick={() => open("wallet")}><Plus className="h-3.5 w-3.5" aria-hidden /> New wallet</button>
            <button type="button" className={BTN} onClick={() => open("transfer")}>Transfer</button>
            <button type="button" className={BTN} onClick={() => open("mint")}>Mint</button>
            <button type="button" className={BTN} onClick={() => { setCheck(null); setNotice(null); void verifyChain().then(setCheck).catch((c) => setNotice(withReason("Chain check failed.", errorReason(c)))); }}>
              <ShieldCheck className="h-3.5 w-3.5" aria-hidden /> Verify chain</button>
          </div>
        )}
      </div>
      {notice && <p role="alert" className="text-xs text-destructive">{notice}</p>}
      {check && <p className={`text-xs ${check.valid ? "text-emerald-400" : "text-destructive"}`}>
        {check.valid ? `Chain valid · ${check.blocks_checked} blocks checked` : `Chain invalid · ${check.errors.join("; ") || "see errors"}`}</p>}
      {mode === "wallet" && (
        <form onSubmit={(e) => { e.preventDefault(); void run(() => createWallet(owner.trim(), Number(start) || 0), "Wallet could not be created."); }}
          className="grid gap-3 rounded-xl border border-border/60 bg-card/20 p-4">
          <label className="grid gap-1 text-xs"><span>Owner</span><input aria-label="Owner" className={FIELD} value={owner} onChange={(e) => setOwner(e.target.value)} /></label>
          <label className="grid gap-1 text-xs"><span>Starting balance</span><input aria-label="Starting balance" type="number" min="0" className={FIELD} value={start} onChange={(e) => setStart(e.target.value)} /></label>
          <div className="flex gap-2">
            <button type="submit" disabled={busy || !owner.trim()} className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">Create wallet</button>
            <button type="button" onClick={() => setMode(null)} className="rounded-md border px-3 py-2 text-xs">Cancel</button>
          </div>
        </form>
      )}
      {(mode === "transfer" || mode === "mint") && (
        <MoneyForm kind={mode} wallets={wallets} busy={busy} onCancel={() => setMode(null)}
          onSubmit={(from, to, amount) => void run(() => (mode === "transfer" ? transfer(from, to, amount) : mint(to, amount)),
            mode === "transfer" ? "Transfer could not be completed." : "Mint could not be completed.")} />
      )}
      {loaded && wallets.length === 0 && mode === null && !notice && (
        <EmptyState icon={Coins} title="No wallets yet" hint="Create a wallet to hold and move tokens." />
      )}
      {wallets.map((w) => (
        <div key={w.wallet_id} className="flex items-center gap-3 rounded-xl border border-border/60 bg-card/20 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate font-mono text-sm font-semibold">{w.wallet_id}</p>
            <p className="truncate text-xs text-muted-foreground">{w.owner_id}</p>
          </div>
          <span className="shrink-0 font-mono text-sm">{w.balance}</span>
        </div>
      ))}
    </section>
  );
}
