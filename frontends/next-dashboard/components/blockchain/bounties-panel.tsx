"use client";

import { useCallback, useEffect, useState } from "react";
import { useMutationRefresh } from "@/components/canvas/refresh-context";
import { Plus, Target, X } from "lucide-react";
import { ConfirmDelete } from "@/components/ui/confirm-delete";
import { EmptyState } from "@/components/ui/empty-state";
import { useMounted } from "@/lib/hooks/use-mounted";
import { listWallets, type Wallet } from "./blockchain-api";
import { bountyFailure, cancelBounty, claimBounty, listBounties, postBounty, type Bounty } from "./bounties-api";

const FIELD = "w-full rounded-md border bg-background/50 px-3 py-2 text-sm";
const STATUS_STYLE: Record<string, string> = {
  open: "bg-emerald-500/10 text-emerald-400", claimed: "bg-sky-500/10 text-sky-400",
};

/** Post, claim and cancel bounties; value moves only after an explicit confirm button. */
export function BountiesPanel() {
  const [bounties, setBounties] = useState<Bounty[]>([]);
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [posting, setPosting] = useState<{ poster: string; amount: string; description: string } | null>(null);
  const [claiming, setClaiming] = useState<{ id: string; wallet: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { version, notify } = useMutationRefresh();
  const mounted = useMounted();

  const refresh = useCallback(async () => {
    try {
      const [b, w] = await Promise.all([listBounties(), listWallets()]);
      if (mounted.current) { setBounties(b); setWallets(w); }
    } catch (cause) { if (mounted.current) setNotice(bountyFailure("Bounties are unavailable.", cause)); }
    finally { if (mounted.current) setLoaded(true); }
  }, [mounted]);
  useEffect(() => { void refresh(); }, [refresh, version]);

  const run = async (action: () => Promise<void>, failure: string) => {
    setBusy(true); setNotice(null);
    try { await action(); setPosting(null); setClaiming(null); await refresh(); notify(); }
    catch (cause) { setNotice(bountyFailure(failure, cause)); }
    finally { setBusy(false); }
  };
  const amount = Number(posting?.amount);
  const canPost = !!posting?.poster && amount > 0 && !!posting.description.trim();

  return (
    <section aria-label="Bounties" className="grid gap-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Bounties</h3>
        {!posting && <button type="button" aria-label="Post bounty" onClick={() => { setNotice(null); setPosting({ poster: "", amount: "", description: "" }); }}
          className="inline-flex items-center gap-1.5 rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-accent/40">
          <Plus className="h-3.5 w-3.5" aria-hidden /> Post bounty</button>}
      </div>
      {notice && <p role="alert" className="text-xs text-destructive">{notice}</p>}
      {posting && (
        <div className="grid gap-3 rounded-xl border border-border/60 bg-card/20 p-4">
          <label className="grid gap-1 text-xs"><span>Poster wallet</span>
            <select aria-label="Poster wallet" className={FIELD} value={posting.poster} onChange={(e) => setPosting({ ...posting, poster: e.target.value })}>
              <option value="">Choose…</option>{wallets.map((w) => <option key={w.wallet_id} value={w.wallet_id}>{w.wallet_id} · {w.balance}</option>)}</select></label>
          <label className="grid gap-1 text-xs"><span>Amount</span>
            <input aria-label="Amount" type="number" min="0" className={FIELD} value={posting.amount} onChange={(e) => setPosting({ ...posting, amount: e.target.value })} /></label>
          <label className="grid gap-1 text-xs"><span>Description</span>
            <input aria-label="Description" className={FIELD} value={posting.description} onChange={(e) => setPosting({ ...posting, description: e.target.value })} /></label>
          <div className="flex gap-2">
            <button type="button" disabled={busy || !canPost} aria-label={canPost ? `Confirm post of ${amount} from ${posting.poster}` : "Confirm post"}
              onClick={() => void run(() => postBounty(posting.poster, amount, posting.description.trim()), "Bounty could not be posted.")}
              className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">{canPost ? `Post ${amount} from ${posting.poster}` : "Post bounty"}</button>
            <button type="button" onClick={() => setPosting(null)} className="rounded-md border px-3 py-2 text-xs">Cancel</button>
          </div>
        </div>
      )}
      {loaded && bounties.length === 0 && !posting && !notice && (
        <EmptyState icon={Target} title="No bounties posted yet" hint="Post one to escrow a reward for whoever completes it." />
      )}
      {bounties.map((b) => (
        <div key={b.bounty_id} className="grid gap-2 rounded-xl border border-border/60 bg-card/20 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{b.description}</p>
              <p className="truncate text-xs text-muted-foreground">
                {b.amount} from {b.poster_wallet}{b.claimer_wallet ? ` · claimed by ${b.claimer_wallet}` : ""}
              </p>
            </div>
            <span className={`rounded-full px-2 py-0.5 text-[10px] ${STATUS_STYLE[b.status] ?? "bg-muted/40 text-muted-foreground"}`}>{b.status}</span>
            {b.status === "open" && (
              <>
                <button type="button" aria-label={`Claim bounty ${b.bounty_id}`} className="rounded-md border border-border/50 px-2 py-1 text-[11px] hover:bg-accent/30"
                  onClick={() => setClaiming({ id: b.bounty_id, wallet: "" })}>Claim</button>
                <ConfirmDelete label={`Cancel bounty ${b.bounty_id}`} disabled={busy}
                  onConfirm={() => void run(() => cancelBounty(b.bounty_id), "Bounty could not be cancelled.")}
                  className="rounded-md p-1.5 text-muted-foreground hover:text-destructive"><X className="h-3.5 w-3.5" /></ConfirmDelete>
              </>
            )}
          </div>
          {claiming?.id === b.bounty_id && (
            <div className="flex items-center gap-2">
              <select aria-label="Claim as wallet" className={FIELD} value={claiming.wallet} onChange={(e) => setClaiming({ ...claiming, wallet: e.target.value })}>
                <option value="">Claim as…</option>{wallets.map((w) => <option key={w.wallet_id} value={w.wallet_id}>{w.wallet_id}</option>)}</select>
              {claiming.wallet && (
                <button type="button" disabled={busy} aria-label={`Confirm claim of ${b.amount} as ${claiming.wallet}`}
                  onClick={() => void run(() => claimBounty(b.bounty_id, claiming.wallet), "Bounty could not be claimed.")}
                  className="shrink-0 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">Claim {b.amount} as {claiming.wallet}</button>
              )}
            </div>
          )}
        </div>
      ))}
    </section>
  );
}
