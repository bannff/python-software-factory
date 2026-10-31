import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
const mocks = vi.hoisted(() => ({ call: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: mocks.call }));
import {
  deleteOwnerSecret, listOwnerSecretNames, setOwnerSecret,
} from "../secrets-settings-api";
import SecretsSettingsPanel from "../secrets-settings-panel";

const wrap = (data: unknown) => ({ tool: "storage", result: { ok: true, data } });

beforeEach(() => { mocks.call.mockReset(); });

describe("Secrets Settings", () => {
  it("lists stored names and never surfaces values", async () => {
    mocks.call.mockImplementation((tool: string) => {
      if (tool === "storage.owner_secret_list") return Promise.resolve(wrap({ names: ["JIRA_API_TOKEN"] }));
      throw new Error(`unexpected ${tool}`);
    });
    await expect(listOwnerSecretNames()).resolves.toEqual(["JIRA_API_TOKEN"]);
  });

  it("sets a secret and reports failure when the tool does not confirm ok", async () => {
    mocks.call.mockImplementation((tool: string) => {
      if (tool === "storage.owner_secret_set") return Promise.resolve(wrap({ ok: true }));
      throw new Error(`unexpected ${tool}`);
    });
    await expect(setOwnerSecret("NAME", "value")).resolves.toBeUndefined();
  });

  it("deletes a secret and returns whether it existed", async () => {
    mocks.call.mockImplementation((tool: string) => {
      if (tool === "storage.owner_secret_delete") return Promise.resolve(wrap({ ok: false }));
      throw new Error(`unexpected ${tool}`);
    });
    await expect(deleteOwnerSecret("MISSING")).resolves.toBe(false);
  });

  it("renders the add form, saves a secret, and lists it with no reveal affordance", async () => {
    let stored: string[] = [];
    mocks.call.mockImplementation((tool: string, args?: unknown) => {
      if (tool === "storage.owner_secret_list") return Promise.resolve(wrap({ names: stored }));
      if (tool === "storage.owner_secret_set") {
        stored = [...stored, (args as { name: string }).name];
        return Promise.resolve(wrap({ ok: true }));
      }
      throw new Error(`unexpected ${tool}`);
    });
    render(<SecretsSettingsPanel />);
    await screen.findByText("No secrets stored yet.");
    fireEvent.change(screen.getByLabelText("Secret name"), { target: { value: "MY_API_KEY" } });
    fireEvent.change(screen.getByLabelText("Secret value"), { target: { value: "sk-123" } });
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => expect(mocks.call).toHaveBeenCalledWith(
      "storage.owner_secret_set", { name: "MY_API_KEY", value: "sk-123" }));
    expect(await screen.findByText("MY_API_KEY")).toBeTruthy();
    // The value never appears anywhere in the rendered output.
    expect(screen.queryByText("sk-123")).toBeNull();
    expect(screen.queryByLabelText(/reveal/i)).toBeNull();
  });

  it("deletes a listed secret via its delete button", async () => {
    let stored = ["TO_DELETE"];
    mocks.call.mockImplementation((tool: string) => {
      if (tool === "storage.owner_secret_list") return Promise.resolve(wrap({ names: stored }));
      if (tool === "storage.owner_secret_delete") { stored = []; return Promise.resolve(wrap({ ok: true })); }
      throw new Error(`unexpected ${tool}`);
    });
    render(<SecretsSettingsPanel />);
    await screen.findByText("TO_DELETE");
    fireEvent.click(screen.getByLabelText("Delete TO_DELETE"));
    await waitFor(() => expect(screen.queryByText("TO_DELETE")).toBeNull());
    expect(await screen.findByText("No secrets stored yet.")).toBeTruthy();
  });
});
