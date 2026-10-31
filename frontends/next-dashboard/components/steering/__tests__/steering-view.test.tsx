import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  list: vi.fn(), read: vi.fn(), save: vi.fn(), remove: vi.fn(),
  legacyAvailable: vi.fn(), caps: vi.fn(),
}));
vi.mock("@/lib/hooks/use-mcp-connection", () => ({ useMcpConnection: () => ({ ready: true, status: "connected" }) }));
vi.mock("../steering-api", () => ({
  listSteering: (...args: unknown[]) => mocks.list(...args), readSteering: (...args: unknown[]) => mocks.read(...args),
  saveSteering: (...args: unknown[]) => mocks.save(...args), steeringAuthoringAvailable: (...args: unknown[]) => mocks.legacyAvailable(...args),
  deleteSteering: (...args: unknown[]) => mocks.remove(...args),
}));
vi.mock("@/lib/authoring-capabilities", async (importOriginal) => ({
  ...(await importOriginal<typeof AuthoringCapabilitiesModule>()),
  getAuthoringCapabilities: (...args: unknown[]) => mocks.caps(...args),
}));

import type * as AuthoringCapabilitiesModule from "@/lib/authoring-capabilities";
import SteeringView from "../steering-view";

const LIFECYCLE = { add: false, create: false, update: false, delete: false, fork: false, reset: false };
const capabilities = (steering: Partial<typeof LIFECYCLE>) => ({
  config: { read: true, write: true },
  skills: { ...LIFECYCLE }, steering: { ...LIFECYCLE, ...steering }, agent_templates: { ...LIFECYCLE },
  roots: {
    config: { path: "/data/agent-config", source: "env" as const },
    skills: { path: "/data/agent-skills", source: "env" as const },
    steering: { path: "/data/agent-steering", source: "env" as const },
  },
});

const row = { id: "quality", title: "Quality", sha256: "a".repeat(64), content: "# Quality\nRun tests." };
beforeEach(() => {
  mocks.list.mockReset().mockResolvedValue([row]);
  mocks.read.mockReset().mockResolvedValue(row);
  mocks.save.mockReset().mockResolvedValue({ ...row, content: "# Quality\nRun all tests.", sha256: "b".repeat(64) });
  mocks.remove.mockReset().mockResolvedValue(undefined);
  mocks.legacyAvailable.mockReset().mockResolvedValue(true);
  mocks.caps.mockReset().mockResolvedValue(capabilities({ create: true, update: true, delete: true }));
});

describe("SteeringView", () => {
  it("reads and revision-fences edits", async () => {
    render(<SteeringView />); fireEvent.click(await screen.findByRole("button", { name: /Quality/ }));
    const editor = await screen.findByLabelText("Markdown");
    fireEvent.change(editor, { target: { value: "# Quality\nRun all tests." } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith({ id: "quality", content: "# Quality\nRun all tests.", expectedSha256: "a".repeat(64) }));
  });

  it("creates only when steering.create is allowed", async () => {
    render(<SteeringView />); fireEvent.click(await screen.findByRole("button", { name: "New steering document" }));
    fireEvent.change(screen.getByLabelText("ID"), { target: { value: "new-doc" } });
    fireEvent.change(screen.getByLabelText("Markdown"), { target: { value: "# New" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith({ id: "new-doc", content: "# New" }));
  });

  it("hides New and names the variable when steering.create is denied", async () => {
    mocks.caps.mockResolvedValue(capabilities({ update: true }));
    render(<SteeringView />);
    expect(await screen.findByText(/FACTORY_AGENT_AUTHORING_STEERING=create/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "New steering document" })).toBeNull();
  });

  it("keeps an existing doc editable when only steering.update is allowed", async () => {
    mocks.caps.mockResolvedValue(capabilities({ update: true }));
    render(<SteeringView />); fireEvent.click(await screen.findByRole("button", { name: /Quality/ }));
    expect(await screen.findByRole("button", { name: "Save" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "New steering document" })).toBeNull();
  });

  it("makes an existing doc read-only and names update when steering.update is denied", async () => {
    mocks.caps.mockResolvedValue(capabilities({ create: true }));
    render(<SteeringView />); fireEvent.click(await screen.findByRole("button", { name: /Quality/ }));
    expect(await screen.findByText(/FACTORY_AGENT_AUTHORING_STEERING=update/)).toBeTruthy();
    expect((screen.getByLabelText("Markdown") as HTMLTextAreaElement).readOnly).toBe(true);
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  });

  it("deletes with its revision when steering.delete is allowed", async () => {
    mocks.caps.mockResolvedValue(capabilities({ update: true, delete: true }));
    render(<SteeringView />); fireEvent.click(await screen.findByRole("button", { name: /Quality/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete steering document" }));
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith("quality", "a".repeat(64)));
  });

  it("shows Delete but not Save when only steering.delete is allowed", async () => {
    mocks.caps.mockResolvedValue(capabilities({ delete: true }));
    render(<SteeringView />); fireEvent.click(await screen.findByRole("button", { name: /Quality/ }));
    expect(await screen.findByRole("button", { name: "Delete steering document" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
    expect(screen.queryByRole("button", { name: "New steering document" })).toBeNull();
  });

  it("hides the delete button while creating a new document", async () => {
    render(<SteeringView />); fireEvent.click(await screen.findByRole("button", { name: "New steering document" }));
    expect(screen.queryByRole("button", { name: "Delete steering document" })).toBeNull();
  });
});
