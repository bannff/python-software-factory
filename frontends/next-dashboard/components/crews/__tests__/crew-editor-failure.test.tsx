import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/hooks/use-personas", () => ({
  usePersonas: () => ({ personas: [{ id: "redteam", name: "Red Team" }], loading: false, error: null, refresh: vi.fn() }),
}));
vi.mock("@/lib/hooks/use-model-catalog", () => ({
  useModelCatalog: () => ({ models: [], groups: [], loading: false, error: null, refresh: vi.fn() }),
}));
const callTool = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ callTool }));

import { CrewEditor } from "../crew-editor";

describe("CrewEditor domain failures", () => {
  it("shows the server's reason and stays open when create resolves ok:false", async () => {
    callTool.mockResolvedValue({ tool: "agent_create_crew", result: { ok: false, error: "crew_exists" } });
    const onSaved = vi.fn();
    const onClose = vi.fn();
    render(<CrewEditor crew={null} isDefault={false} onSaved={onSaved} onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: /create|save/i }));
    expect((await screen.findByRole("alert")).textContent).toContain("crew_exists");
    await waitFor(() => expect(callTool).toHaveBeenCalled());
    expect(onSaved).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });
});
