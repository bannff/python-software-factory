import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  list: vi.fn(), add: vi.fn(), importDoc: vi.fn(), update: vi.fn(), remove: vi.fn(), reload: vi.fn(),
}));
vi.mock("@/lib/api", () => ({ callTool: vi.fn() }));
vi.mock("../connections-api", () => ({ reloadCapabilities: (...a: unknown[]) => mocks.reload(...a) }));
vi.mock("../external-servers-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../external-servers-api")>()),
  listExternalServers: (...a: unknown[]) => mocks.list(...a),
  addExternalServer: (...a: unknown[]) => mocks.add(...a),
  importExternalServers: (...a: unknown[]) => mocks.importDoc(...a),
  updateExternalServer: (...a: unknown[]) => mocks.update(...a),
  removeExternalServer: (...a: unknown[]) => mocks.remove(...a),
}));

import { ExternalServersPanel } from "../external-servers-panel";

const GITHUB = {
  name: "github", transport: "stdio" as const, command: "npx", args: ["-y", "server-github"], cwd: null,
  env: { GITHUB_TOKEN: "GH_SOURCE_ENV" }, url: null, headers: {}, enabled: true, mounted: true, unresolvedEnv: [],
  toolsCount: 7, revision: 3,
};

beforeEach(() => {
  Object.values(mocks).forEach((fn) => fn.mockReset().mockResolvedValue(undefined));
  mocks.list.mockResolvedValue([GITHUB]);
});

describe("ExternalServersPanel", () => {
  it("adds a stdio server from the form with env-name references", async () => {
    const onChanged = vi.fn();
    render(<ExternalServersPanel ready onChanged={onChanged} />);
    fireEvent.click(await screen.findByRole("button", { name: /Add server/ }));
    fireEvent.change(screen.getByLabelText("Server name"), { target: { value: "fetch" } });
    fireEvent.change(screen.getByLabelText("Command"), { target: { value: "uvx" } });
    fireEvent.change(screen.getByLabelText("Arguments"), { target: { value: "mcp-server-fetch --x" } });
    fireEvent.change(screen.getByLabelText("Environment"), { target: { value: "API_KEY=FETCH_KEY_ENV" } });
    fireEvent.submit(screen.getByRole("dialog").querySelector("form")!);
    await waitFor(() => expect(mocks.add).toHaveBeenCalledWith("fetch", {
      transport: "stdio", command: "uvx", args: ["mcp-server-fetch", "--x"], env: { API_KEY: "FETCH_KEY_ENV" }, enabled: true,
    }));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("imports a pasted mcpServers document", async () => {
    render(<ExternalServersPanel ready onChanged={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: /Add server/ }));
    fireEvent.click(screen.getByRole("tab", { name: "JSON" }));
    const doc = '{"mcpServers":{"a":{"command":"x"}}}';
    fireEvent.change(screen.getByLabelText("mcpServers JSON"), { target: { value: doc } });
    fireEvent.submit(screen.getByRole("dialog").querySelector("form")!);
    await waitFor(() => expect(mocks.importDoc).toHaveBeenCalledWith(doc));
  });

  it("toggles enabled with the exact stored spec and CAS revision", async () => {
    render(<ExternalServersPanel ready onChanged={vi.fn()} />);
    fireEvent.click(await screen.findByLabelText("Enable github"));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith("github", {
      transport: "stdio", command: "npx", args: ["-y", "server-github"], env: { GITHUB_TOKEN: "GH_SOURCE_ENV" }, enabled: false,
    }, 3));
  });

  it("removes with CAS revision and reloads capabilities", async () => {
    render(<ExternalServersPanel ready onChanged={vi.fn()} />);
    fireEvent.click(await screen.findByLabelText("Remove github"));
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith("github", 3));
    fireEvent.click(screen.getByRole("button", { name: "Reload capabilities" }));
    await waitFor(() => expect(mocks.reload).toHaveBeenCalled());
    expect(screen.getByText("7 tools")).toBeTruthy();
  });

  it("surfaces a typed failure from the server", async () => {
    mocks.reload.mockRejectedValueOnce(new Error("connections_identity_required"));
    render(<ExternalServersPanel ready onChanged={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Reload capabilities" }));
    expect((await screen.findByRole("alert")).textContent).toContain("connections_identity_required");
  });
});
