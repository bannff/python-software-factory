import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { AuthoredPromptsPanel } from "../authored-prompts-panel";
import { validatePromptForm } from "../prompt-validation";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
const record = { prompt_id: "triage", description: "Triage a finding", template: "Look at {finding}",
  arguments: [{ name: "finding", description: "", required: true }], revision: 3 };
const typed = (code: string) => Object.assign(new Error(code), { reason: code });

beforeEach(() => callTool.mockReset());

describe("validatePromptForm", () => {
  const form = { prompt_id: "triage", description: "", template: "hello", args: [] as { name: string; description: string; required: boolean }[] };
  it("accepts a valid form", () => expect(validatePromptForm(form, true)).toEqual({}));
  it("checks the id on create only, and requires a template", () => {
    expect(validatePromptForm({ ...form, prompt_id: "Bad Id" }, true).prompt_id).toBeTruthy();
    expect(validatePromptForm({ ...form, prompt_id: "Bad Id" }, false).prompt_id).toBeUndefined();
    expect(validatePromptForm({ ...form, template: " " }, true).template).toBeTruthy();
  });
  it("names a placeholder that is not a declared argument", () => {
    const err = validatePromptForm({ ...form, template: "Review {finding} for {owner}" }, true).template;
    expect(err).toMatch(/finding/);
    expect(err).toMatch(/owner/);
    const declared = [{ name: "finding", description: "", required: true }, { name: "owner", description: "", required: false }];
    expect(validatePromptForm({ ...form, template: "Review {finding} for {owner}", args: declared }, true)).toEqual({});
  });
  it("rejects duplicate argument names", () => {
    const dup = { name: "a", description: "", required: false };
    expect(validatePromptForm({ ...form, args: [dup, dup] }, true).args).toMatch(/duplicate/i);
  });
  it("rejects a bad argument name", () => {
    expect(validatePromptForm({ ...form, args: [{ name: "Bad-Name", description: "", required: false }] }, true).args).toBeTruthy();
  });
});

describe("AuthoredPromptsPanel", () => {
  it("lists authored prompts and shows an empty state with a create action", async () => {
    callTool.mockResolvedValueOnce(ok({ count: 0, prompts: [] }));
    render(<AuthoredPromptsPanel />);
    expect(await screen.findByText("No prompts of your own yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "New prompt" })).toBeTruthy();
  });

  it("creates a prompt and refreshes the list", async () => {
    callTool.mockResolvedValueOnce(ok({ count: 0, prompts: [] }))
      .mockResolvedValueOnce(ok({ prompt: record }))
      .mockResolvedValueOnce(ok({ count: 1, prompts: [record] }));
    render(<AuthoredPromptsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "New prompt" }));
    fireEvent.change(screen.getByLabelText("Prompt ID"), { target: { value: "triage" } });
    fireEvent.change(screen.getByLabelText("Template"), { target: { value: "Look at it" } });
    fireEvent.click(screen.getByRole("button", { name: "Save prompt" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("agent_add_prompt",
      { prompt_id: "triage", description: "", template: "Look at it", arguments: [] }));
    expect(await screen.findByText("triage")).toBeTruthy();
  });

  it("puts a prompt_exists refusal on the ID field", async () => {
    callTool.mockResolvedValueOnce(ok({ count: 0, prompts: [] })).mockRejectedValueOnce(typed("prompt_exists"));
    render(<AuthoredPromptsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "New prompt" }));
    fireEvent.change(screen.getByLabelText("Prompt ID"), { target: { value: "triage" } });
    fireEvent.change(screen.getByLabelText("Template"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Save prompt" }));
    expect(await screen.findByText(/already exists/i)).toBeTruthy();
  });

  it("edits with the expected revision and deletes after confirmation", async () => {
    callTool.mockResolvedValueOnce(ok({ count: 1, prompts: [record] }))
      .mockResolvedValueOnce(ok({ prompt: { ...record, revision: 4 } }))
      .mockResolvedValueOnce(ok({ count: 1, prompts: [{ ...record, revision: 4 }] }))
      .mockResolvedValueOnce(ok({ prompt_id: "triage", deleted: true }))
      .mockResolvedValueOnce(ok({ count: 0, prompts: [] }));
    render(<AuthoredPromptsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit prompt triage" }));
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Better" } });
    fireEvent.click(screen.getByRole("button", { name: "Save prompt" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("agent_update_prompt",
      expect.objectContaining({ prompt_id: "triage", expected_revision: 3, description: "Better" })));
    fireEvent.click(await screen.findByRole("button", { name: "Delete prompt triage" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete prompt triage" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("agent_delete_prompt", { prompt_id: "triage" }));
    expect(await screen.findByText("No prompts of your own yet")).toBeTruthy();
  });

  it("tells the user to reload on a revision conflict", async () => {
    callTool.mockResolvedValueOnce(ok({ count: 1, prompts: [record] })).mockRejectedValueOnce(typed("prompt_revision_conflict"));
    render(<AuthoredPromptsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit prompt triage" }));
    fireEvent.click(screen.getByRole("button", { name: "Save prompt" }));
    expect(await screen.findByText(/changed elsewhere/i)).toBeTruthy();
  });
});
