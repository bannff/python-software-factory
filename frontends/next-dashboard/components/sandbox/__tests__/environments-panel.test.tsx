import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { EnvironmentsPanel } from "../environments-panel";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
const env = (id: string, status: string, profile?: string) => ({ env_id: id, status, instance_type: "docker", public_ip: status === "running" ? "10.0.0.1" : null,
  created_at: "2026-11-03T15:00:00Z", metadata: profile ? { profile } : {} });
let envs: unknown[] = [];

beforeEach(() => {
  callTool.mockReset(); envs = [];
  callTool.mockImplementation(async (name: string) => {
    if (name === "sandbox_list_environments") return ok({ environments: envs, count: envs.length });
    if (name === "sandbox_list_profiles") return ok({ profiles: { dvwa: {}, webgoat: {} } });
    if (name === "sandbox_list_device_presets") return ok({ presets: { "pixel-8": {}, "iphone-15": {} } });
    if (name === "sandbox_get_status") return ok({ found: true, environment: env("env-p", "running", "dvwa") });
    if (name === "sandbox_terminate") return ok({ success: true, env_id: "env-1" });
    return ok({ success: true, environment: env("env-new", "provisioning") });
  });
});

describe("EnvironmentsPanel", () => {
  it("offers a first environment when there are none", async () => {
    render(<EnvironmentsPanel />);
    expect(await screen.findByText("No environments yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "New environment" })).toBeTruthy();
  });

  it("provisions with the chosen profile only", async () => {
    render(<EnvironmentsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "New environment" }));
    await screen.findByRole("option", { name: "dvwa" });
    fireEvent.change(screen.getByLabelText("Profile"), { target: { value: "dvwa" } });
    fireEvent.click(screen.getByRole("button", { name: "Provision" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("sandbox_provision", { profile: "dvwa" }));
  });

  it("provisions a default environment when nothing is chosen", async () => {
    render(<EnvironmentsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "New environment" }));
    await screen.findByRole("option", { name: "dvwa" });
    fireEvent.click(screen.getByRole("button", { name: "Provision" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("sandbox_provision", {}));
  });

  it("lists environments with status, address and profile; terminated ones are dimmed and offer no Terminate", async () => {
    envs = [env("env-1", "running", "dvwa"), env("env-2", "terminated", "webgoat")];
    render(<EnvironmentsPanel />);
    expect(await screen.findByText("env-1")).toBeTruthy();
    expect(screen.getByText(/10\.0\.0\.1/)).toBeTruthy();
    expect(screen.getByText(/dvwa/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Terminate environment env-1" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Terminate environment env-2" })).toBeNull();
  });

  it("terminates after confirmation", async () => {
    envs = [env("env-1", "running")];
    render(<EnvironmentsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Terminate environment env-1" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm terminate environment env-1" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("sandbox_terminate", { env_id: "env-1" }));
  });

  it("explains an opaque provisioning failure without blaming one cause", async () => {
    render(<EnvironmentsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "New environment" }));
    await screen.findByRole("option", { name: "dvwa" });
    callTool.mockImplementation(async (name: string) => {
      if (name === "sandbox_list_environments") return ok({ environments: [], count: 0 });
      if (name === "sandbox_provision") throw new Error("tool_execution_failed");
      return ok({});
    });
    fireEvent.click(screen.getByRole("button", { name: "Provision" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/could not be provisioned/i);
    expect(alert.textContent).not.toMatch(/tool_execution_failed/);
  });

  it("checks the status of a provisioning environment so it does not look stuck", async () => {
    envs = [env("env-p", "provisioning", "dvwa")];
    render(<EnvironmentsPanel />);
    expect(await screen.findByText("running")).toBeTruthy();
    expect(callTool).toHaveBeenCalledWith("sandbox_get_status", { env_id: "env-p" });
  });

  it("keeps the listed status when the status check fails", async () => {
    envs = [env("env-p", "provisioning")];
    callTool.mockImplementation(async (name: string) => {
      if (name === "sandbox_list_environments") return ok({ environments: envs, count: 1 });
      throw new Error("tool_execution_failed");
    });
    render(<EnvironmentsPanel />);
    expect(await screen.findByText("provisioning")).toBeTruthy();
  });
});
