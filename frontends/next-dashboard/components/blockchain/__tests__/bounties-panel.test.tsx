import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { BountiesPanel } from "../bounties-panel";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
const wallets = [{ wallet_id: "wallet-a", owner_id: "alice", balance: 100 }, { wallet_id: "wallet-b", owner_id: "bob", balance: 5 }];
const bounty = (id: string, status: string, claimer: string | null = null) => ({
  success: true, bounty_id: id, poster_wallet: "wallet-a", amount: 4, description: "Fix the login bug", criteria: {}, status, claimer_wallet: claimer, error: null,
});
let bounties: unknown[] = [];

beforeEach(() => {
  callTool.mockReset(); bounties = [];
  callTool.mockImplementation(async (name: string) => {
    if (name === "blockchain_list_wallets") return ok({ count: 2, wallets });
    if (name === "blockchain_list_bounties") return ok({ count: bounties.length, bounties });
    return ok({ success: true, tx_id: "tx-1", bounty_id: "bounty-new" });
  });
});

describe("BountiesPanel", () => {
  it("offers a first bounty when there are none", async () => {
    render(<BountiesPanel />);
    expect(await screen.findByText("No bounties posted yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Post bounty" })).toBeTruthy();
  });

  it("lists bounties with status, amount and who holds them", async () => {
    bounties = [bounty("bounty-1", "open"), bounty("bounty-2", "claimed", "wallet-b")];
    render(<BountiesPanel />);
    expect(await screen.findAllByText("Fix the login bug")).toHaveLength(2);
    expect(screen.getByText(/claimed by wallet-b/i)).toBeTruthy();
  });

  it("posts a bounty from a chosen wallet with an empty criteria object", async () => {
    render(<BountiesPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Post bounty" }));
    await screen.findByRole("option", { name: /wallet-a/ });
    fireEvent.change(screen.getByLabelText("Poster wallet"), { target: { value: "wallet-a" } });
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Fix the login bug" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm post of 4 from wallet-a" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("blockchain_post_bounty",
      { poster_wallet: "wallet-a", amount: 4, description: "Fix the login bug", criteria: {} }));
  });

  it("claims an open bounty only after naming the wallet and confirming", async () => {
    bounties = [bounty("bounty-1", "open")];
    render(<BountiesPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Claim bounty bounty-1" }));
    fireEvent.change(screen.getByLabelText("Claim as wallet"), { target: { value: "wallet-b" } });
    expect(callTool).not.toHaveBeenCalledWith("blockchain_claim_bounty", expect.anything());
    fireEvent.click(screen.getByRole("button", { name: "Confirm claim of 4 as wallet-b" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("blockchain_claim_bounty", { bounty_id: "bounty-1", claimer_wallet: "wallet-b" }));
  });

  it("cancels an open bounty after confirmation and offers nothing on a claimed one", async () => {
    bounties = [bounty("bounty-1", "open"), bounty("bounty-2", "claimed", "wallet-b")];
    render(<BountiesPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Cancel bounty bounty-1" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm cancel bounty bounty-1" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("blockchain_cancel_bounty", { bounty_id: "bounty-1" }));
    expect(screen.queryByRole("button", { name: "Cancel bounty bounty-2" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Claim bounty bounty-2" })).toBeNull();
  });

  it("turns the ledger's refusals into plain sentences", async () => {
    bounties = [bounty("bounty-1", "open")];
    callTool.mockImplementation(async (name: string) => {
      if (name === "blockchain_list_wallets") return ok({ count: 2, wallets });
      if (name === "blockchain_list_bounties") return ok({ count: 1, bounties });
      return ok({ success: false, error: "Bounty not open: BountyStatus.CLAIMED" });
    });
    render(<BountiesPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Claim bounty bounty-1" }));
    fireEvent.change(screen.getByLabelText("Claim as wallet"), { target: { value: "wallet-b" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm claim of 4 as wallet-b" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/already been claimed or closed/i);
    expect(alert.textContent).not.toMatch(/BountyStatus/);
  });
});
