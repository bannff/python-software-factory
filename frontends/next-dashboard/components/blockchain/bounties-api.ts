import { callTool } from "@/lib/api";
import { errorReason, withReason } from "@/lib/error-reason";
import { unwrapToolData } from "@/lib/tool-result-data";
import { refuseIfFailed } from "./blockchain-api";

export interface Bounty {
  bounty_id: string; poster_wallet: string; amount: number; description: string;
  status: string; claimer_wallet: string | null;
}

const str = (v: unknown) => (typeof v === "string" ? v : "");

export async function listBounties(): Promise<Bounty[]> {
  const data = unwrapToolData(await callTool("blockchain_list_bounties", { status: "", limit: 50 })) as { bounties?: unknown };
  return Array.isArray(data?.bounties) ? data.bounties.flatMap((b): Bounty[] => {
    const v = b as Record<string, unknown>;
    return typeof v?.bounty_id === "string"
      ? [{ bounty_id: v.bounty_id, poster_wallet: str(v.poster_wallet), amount: typeof v.amount === "number" ? v.amount : 0,
          description: str(v.description), status: str(v.status), claimer_wallet: typeof v.claimer_wallet === "string" ? v.claimer_wallet : null }]
      : [];
  }) : [];
}

export async function postBounty(poster: string, amount: number, description: string): Promise<void> {
  refuseIfFailed(unwrapToolData(await callTool("blockchain_post_bounty",
    { poster_wallet: poster, amount, description, criteria: {} })));
}
export async function claimBounty(bountyId: string, claimer: string): Promise<void> {
  refuseIfFailed(unwrapToolData(await callTool("blockchain_claim_bounty", { bounty_id: bountyId, claimer_wallet: claimer })));
}
export async function cancelBounty(bountyId: string): Promise<void> {
  refuseIfFailed(unwrapToolData(await callTool("blockchain_cancel_bounty", { bounty_id: bountyId })));
}

/** The ledger refuses in free text (and leaks enum names); say it in plain words. */
const REFUSALS: [RegExp, string][] = [
  [/bounty not open/i, "This bounty has already been claimed or closed."],
  [/bounty not found/i, "This bounty no longer exists."],
  [/cannot cancel/i, "Only an open bounty can be cancelled."],
  [/invalid bounty/i, "That wallet can't fund this amount. Check its balance."],
];

export function bountyFailure(prose: string, cause: unknown): string {
  const reason = errorReason(cause) ?? "";
  const known = REFUSALS.find(([pattern]) => pattern.test(reason));
  return known ? known[1] : withReason(prose, reason || undefined);
}
