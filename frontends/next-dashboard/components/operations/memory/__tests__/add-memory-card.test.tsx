import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import AddMemoryCard from "../add-memory-card";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
const onSaved = vi.fn();
beforeEach(() => { callTool.mockReset(); onSaved.mockReset(); });

const open = () => fireEvent.click(screen.getByRole("button", { name: "Add a memory" }));
const type = (text: string) => fireEvent.change(screen.getByLabelText("Memory"), { target: { value: text } });
const save = () => fireEvent.click(screen.getByRole("button", { name: "Save memory" }));

describe("AddMemoryCard", () => {
  it("asks for some text before saving", async () => {
    render(<AddMemoryCard onSaved={onSaved} />);
    open(); save();
    expect((await screen.findByRole("alert")).textContent).toMatch(/enter/i);
    expect(callTool).not.toHaveBeenCalled();
  });

  it("stores the text with the chosen type and refreshes the list", async () => {
    callTool.mockResolvedValue(ok({ stored: true, memory_id: "m1" }));
    render(<AddMemoryCard onSaved={onSaved} />);
    open(); type("I prefer concise answers");
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "long_term" } });
    save();
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    expect(callTool).toHaveBeenCalledWith("memory_store", { content: "I prefer concise answers", memory_type: "long_term" });
    expect(screen.queryByLabelText("Memory")).toBeNull();
  });

  it("shows the server's reason when nothing was stored", async () => {
    callTool.mockResolvedValue(ok({ stored: false, error: "protected content requires an approved projection" }));
    render(<AddMemoryCard onSaved={onSaved} />);
    open(); type("secret"); save();
    expect((await screen.findByRole("alert")).textContent).toMatch(/could not be saved.*protected content/i);
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("shows a friendly error when the call fails", async () => {
    callTool.mockImplementation(async () => { throw new Error("boom"); });
    render(<AddMemoryCard onSaved={onSaved} />);
    open(); type("x"); save();
    expect((await screen.findByRole("alert")).textContent).toMatch(/could not be saved/i);
  });
});
