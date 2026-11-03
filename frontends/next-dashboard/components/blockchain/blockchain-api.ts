import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface Wallet { wallet_id: string; owner_id: string; balance: number }
export interface ChainCheck { valid: boolean; blocks_checked: number; errors: string[] }

/** Ledger tools may refuse inside a successful envelope (`success:false, error`); surface that as a failure. */
function refuseIfFailed(data: unknown): void {
  const v = data as { success?: unknown; error?: unknown } | null;
  if (v?.success === false) throw new Error(typeof v.error === "string" ? v.error : "The ledger refused this request.");
}

export async function listWallets(): Promise<Wallet[]> {
  const data = unwrapToolData(await callTool("blockchain_list_wallets", { limit: 100 })) as { wallets?: unknown };
  return Array.isArray(data?.wallets) ? data.wallets.flatMap((w): Wallet[] => {
    const v = w as Record<string, unknown>;
    return typeof v?.wallet_id === "string"
      ? [{ wallet_id: v.wallet_id, owner_id: typeof v.owner_id === "string" ? v.owner_id : "", balance: typeof v.balance === "number" ? v.balance : 0 }]
      : [];
  }) : [];
}

export async function createWallet(ownerId: string, initialBalance: number): Promise<void> {
  refuseIfFailed(unwrapToolData(await callTool("blockchain_create_wallet", { owner_id: ownerId, initial_balance: initialBalance })));
}
export async function transfer(from: string, to: string, amount: number): Promise<void> {
  refuseIfFailed(unwrapToolData(await callTool("blockchain_transfer", { from_wallet: from, to_wallet: to, amount })));
}
export async function mint(to: string, amount: number): Promise<void> {
  refuseIfFailed(unwrapToolData(await callTool("blockchain_mint", { to_wallet: to, amount })));
}
export async function verifyChain(): Promise<ChainCheck> {
  const d = unwrapToolData(await callTool("blockchain_verify_chain")) as Partial<ChainCheck> | null;
  return { valid: d?.valid === true, blocks_checked: typeof d?.blocks_checked === "number" ? d.blocks_checked : 0,
    errors: Array.isArray(d?.errors) ? d.errors.map(String) : [] };
}
