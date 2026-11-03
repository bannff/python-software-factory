import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { BlockchainPanel } from "../blockchain-panel";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
const wallet = (id: string, owner: string, balance: number) => ({ wallet_id: id, owner_id: owner, balance, created_at: "2026-01-01T00:00:00Z" });
let wallets: unknown[] = [];
beforeEach(() => {
  callTool.mockReset(); wallets = [];
  callTool.mockImplementation(async (name: string) => {
    if (name === "blockchain_list_wallets") return ok({ count: wallets.length, wallets });
    if (name === "blockchain_verify_chain") return ok({ valid: true, blocks_checked: 7, errors: [] });
    return ok({ success: true, tx_id: "tx-1", wallet_id: "wallet-new", balance: 0 });
  });
});

describe("BlockchainPanel", () => {
  it("offers a first wallet when there are none", async () => {
    render(<BlockchainPanel />);
    expect(await screen.findByText("No wallets yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "New wallet" })).toBeTruthy();
  });

  it("lists wallets with owner and balance", async () => {
    wallets = [wallet("wallet-a", "alice", 150)];
    render(<BlockchainPanel />);
    expect(await screen.findByText("wallet-a")).toBeTruthy();
    expect(screen.getByText(/alice/)).toBeTruthy();
    expect(screen.getByText(/150/)).toBeTruthy();
  });

  it("creates a wallet for an owner with a starting balance", async () => {
    render(<BlockchainPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "New wallet" }));
    fireEvent.change(screen.getByLabelText("Owner"), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText("Starting balance"), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "Create wallet" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("blockchain_create_wallet", { owner_id: "alice", initial_balance: 100 }));
  });

  it("asks for confirmation before moving money, then transfers", async () => {
    wallets = [wallet("wallet-a", "alice", 150), wallet("wallet-b", "bob", 0)];
    render(<BlockchainPanel />);
    await screen.findByText("wallet-a");
    fireEvent.click(screen.getByRole("button", { name: "Transfer" }));
    fireEvent.change(screen.getByLabelText("From wallet"), { target: { value: "wallet-a" } });
    fireEvent.change(screen.getByLabelText("To wallet"), { target: { value: "wallet-b" } });
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "25" } });
    fireEvent.click(screen.getByRole("button", { name: "Review transfer" }));
    expect(callTool).not.toHaveBeenCalledWith("blockchain_transfer", expect.anything());
    fireEvent.click(screen.getByRole("button", { name: "Confirm transfer of 25 from wallet-a to wallet-b" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("blockchain_transfer", { from_wallet: "wallet-a", to_wallet: "wallet-b", amount: 25 }));
  });

  it("mints after confirmation", async () => {
    wallets = [wallet("wallet-a", "alice", 0)];
    render(<BlockchainPanel />);
    await screen.findByText("wallet-a");
    fireEvent.click(screen.getByRole("button", { name: "Mint" }));
    fireEvent.change(screen.getByLabelText("To wallet"), { target: { value: "wallet-a" } });
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "50" } });
    fireEvent.click(screen.getByRole("button", { name: "Review mint" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm mint of 50 to wallet-a" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("blockchain_mint", { to_wallet: "wallet-a", amount: 50 }));
  });

  it("reports a refused transfer from the success body", async () => {
    wallets = [wallet("wallet-a", "alice", 1), wallet("wallet-b", "bob", 0)];
    callTool.mockImplementation(async (name: string) => {
      if (name === "blockchain_list_wallets") return ok({ count: 2, wallets });
      return ok({ success: false, error: "Insufficient balance" });
    });
    render(<BlockchainPanel />);
    await screen.findByText("wallet-a");
    fireEvent.click(screen.getByRole("button", { name: "Transfer" }));
    fireEvent.change(screen.getByLabelText("From wallet"), { target: { value: "wallet-a" } });
    fireEvent.change(screen.getByLabelText("To wallet"), { target: { value: "wallet-b" } });
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "999" } });
    fireEvent.click(screen.getByRole("button", { name: "Review transfer" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm transfer of 999 from wallet-a to wallet-b" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Insufficient balance");
  });

  it("verifies the chain and says what it found", async () => {
    render(<BlockchainPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Verify chain" }));
    expect(await screen.findByText(/valid.*7 blocks/i)).toBeTruthy();
  });
});
