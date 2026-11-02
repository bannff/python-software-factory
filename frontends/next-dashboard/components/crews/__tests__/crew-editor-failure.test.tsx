import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/hooks/use-personas", () => ({
  usePersonas: () => ({ personas: [{ id: "redteam", name: "Red Team" }], loading: false, error: null, refresh: vi.fn() }),
}));
vi.mock("@/lib/hooks/use-project-roots", () => ({ useProjectRoots: () => ({ roots: [], loading: false }) }));
vi.mock("@/lib/hooks/use-model-catalog", () => ({
  useModelCatalog: () => ({ models: [], groups: [], loading: false, error: null, refresh: vi.fn() }),
}));
const callTool = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ callTool, listTools: () => Promise.resolve({ tools: [] }) }));

import { CrewEditor } from "../crew-editor";

describe("CrewEditor domain failures", () => {
  it("shows the server's reason and stays open when create resolves ok:false", async () => {
    callTool.mockResolvedValue({ tool: "agent_create_crew", result: { ok: false, error: "crew_exists" } });
    const onSaved = vi.fn();
    const onClose = vi.fn();
    render(<CrewEditor crew={null} isDefault={false} onSaved={onSaved} onClose={onClose} />);
    const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
    fill("Crew ID", "alpha"); fill("Name", "Alpha"); fill("Persona", "redteam");
    fill("Project path", "/work/app"); fill("Memory scope", "alpha");
    fireEvent.click(screen.getByRole("button", { name: /create|save/i }));
    expect((await screen.findByRole("alert")).textContent).toContain("crew_exists");
    await waitFor(() => expect(callTool).toHaveBeenCalled());
    expect(onSaved).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("shows the server's reason and stays open when set-default resolves ok:false", async () => {
    callTool.mockResolvedValue({ tool: "agent_set_default_crew", result: { ok: false, error: "crew_not_found" } });
    const onSaved = vi.fn();
    const onClose = vi.fn();
    const crew = { id: "alpha", name: "Alpha", persona_id: "redteam", project: "/work/app", memory_scope: "alpha", revision: 1 };
    render(<CrewEditor crew={crew as never} isDefault={false} onSaved={onSaved} onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: /set as default/i }));
    expect((await screen.findByRole("alert")).textContent).toContain("crew_not_found");
    expect(onSaved).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("puts a refused project path on the Project field and keeps the form", async () => {
    callTool.mockResolvedValue({ tool: "agent_create_crew", result: { ok: false, error: "crew_project_path_refused" } });
    render(<CrewEditor crew={null} isDefault={false} onSaved={vi.fn()} onClose={vi.fn()} />);
    const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
    fill("Crew ID", "alpha"); fill("Name", "Alpha"); fill("Persona", "redteam");
    fill("Project path", "/tmp"); fill("Memory scope", "alpha");
    fireEvent.click(screen.getByRole("button", { name: /create|save/i }));
    const project = screen.getByLabelText("Project path");
    await waitFor(() => expect(project.getAttribute("aria-invalid")).toBe("true"));
    expect(document.getElementById("crew-project-control-error")?.textContent).toMatch(/allowed project root/i);
    expect((project as HTMLInputElement).value).toBe("/tmp");
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Alpha");
    expect(screen.queryByText(/Couldn’t create this crew/)).toBeNull();
  });
});
