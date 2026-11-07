import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const { callTool } = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool }));

import { CrewDelete } from "../crew-delete";
import type { Crew } from "../crew-types";

const crew = { id: "red", name: "Red Team", revision: 3 } as Crew;
const envelope = (data: unknown) => ({ tool: "x", result: { schema_version: "v1", ok: true, data } });
const failure = (error: string) => ({ tool: "x", result: { schema_version: "v1", ok: false, data: null, error } });

beforeEach(() => {
  callTool.mockReset();
});

describe("CrewDelete", () => {
  it("deletes with the revision fence only after confirmation", async () => {
    callTool.mockResolvedValue(envelope({ crew_id: "red", deleted: true }));
    const onDeleted = vi.fn();
    render(<CrewDelete crew={crew} onDeleted={onDeleted} />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete crew Red Team" }));
    expect(callTool).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete crew Red Team" }));
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
    expect(callTool).toHaveBeenCalledWith("agent_delete_crew", { crew_id: "red", expected_revision: 3 });
  });

  it("shows the server's reason and keeps the crew when the delete fails", async () => {
    callTool.mockResolvedValue(failure("crew_revision_conflict"));
    const onDeleted = vi.fn();
    render(<CrewDelete crew={crew} onDeleted={onDeleted} />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete crew Red Team" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete crew Red Team" }));
    expect((await screen.findByRole("alert")).textContent).toContain("crew_revision_conflict");
    expect(onDeleted).not.toHaveBeenCalled();
  });
});
