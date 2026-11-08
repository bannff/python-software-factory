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

/** Answer by tool name so the test fails if the picker asks the roots tool. */
function serve(roots: string[], projects: string[]) {
  callTool.mockImplementation(async (tool: string) =>
    tool === "devtools_list_projects"
      ? { tool, result: { ok: true, data: { projects } } }
      : { tool, result: { ok: true, data: { roots } } });
}

function open() {
  return render(<CrewEditor crew={null} isDefault={false} onSaved={vi.fn()} onClose={vi.fn()} />);
}

describe("CrewEditor required fields", () => {
  it("marks each missing field and does not call the server", async () => {
    serve([], []);
    open();
    fireEvent.change(screen.getByLabelText("Crew ID"), { target: { value: "alpha" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Alpha" } });
    fireEvent.click(screen.getByRole("button", { name: /create crew/i }));
    expect(await screen.findByText(/pick a persona/i)).toBeTruthy();
    expect(screen.getByLabelText("Persona").getAttribute("aria-invalid")).toBe("true");
    expect(callTool).not.toHaveBeenCalledWith("agent_create_crew", expect.anything());
  });

  it("offers the projects inside the allowed roots, not the roots themselves", async () => {
    serve(["/work"], ["/work/a", "/work/b"]);
    open();
    await waitFor(() => expect(screen.getByLabelText("Project path").tagName).toBe("SELECT"));
    const picker = screen.getByLabelText("Project path");
    expect(Array.from(picker.querySelectorAll("option")).map((o) => o.textContent)).toEqual(
      ["Select a project…", "/work/a", "/work/b"],
    );
  });

  it("falls back to a text input when no projects are admissible", async () => {
    serve(["/work"], []);
    open();
    expect((await screen.findByLabelText("Project path")).tagName).toBe("INPUT");
  });
});
