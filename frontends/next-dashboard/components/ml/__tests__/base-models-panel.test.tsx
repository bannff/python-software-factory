import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { BaseModelsPanel } from "../base-models-panel";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
const model = { name: "tiny", model_id: "org/tiny-llama", description: "Small", recommended_method: "lora" };
let models: unknown[] = [];
const typed = (code: string) => Object.assign(new Error(code), { reason: code });

beforeEach(() => {
  callTool.mockReset(); models = [];
  callTool.mockImplementation(async (name: string) => {
    if (name === "ml_list_base_models") return ok({ count: models.length, models });
    if (name === "ml_list_finetuning_methods") return ok({ methods: [{ name: "lora", description: "" }, { name: "ia3", description: "" }] });
    return ok({ ok: true, model, name: "tiny", deleted: true });
  });
});

describe("BaseModelsPanel", () => {
  it("offers a first base model when there are none", async () => {
    render(<BaseModelsPanel />);
    expect(await screen.findByText("No base models registered yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Register base model" })).toBeTruthy();
  });

  it("registers a base model with the recommended method", async () => {
    render(<BaseModelsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Register base model" }));
    await screen.findByRole("option", { name: "ia3" });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "tiny" } });
    fireEvent.change(screen.getByLabelText("Model ID"), { target: { value: "org/tiny-llama" } });
    fireEvent.change(screen.getByLabelText("Recommended method"), { target: { value: "ia3" } });
    fireEvent.click(screen.getByRole("button", { name: "Save base model" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("ml_register_base_model",
      { name: "tiny", model_id: "org/tiny-llama", description: "", recommended_method: "ia3" }));
  });

  it("explains that editing is switched off instead of showing the raw message", async () => {
    render(<BaseModelsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Register base model" }));
    await screen.findByRole("option", { name: "ia3" });
    callTool.mockImplementation(async (name: string) => {
      if (name === "ml_list_base_models") return ok({ count: 0, models: [] });
      if (name === "ml_list_finetuning_methods") return ok({ methods: [{ name: "lora", description: "" }] });
      throw new Error("Authoring tools disabled. Set ML_ENABLE_AUTHORING_TOOLS=1");
    });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "tiny" } });
    fireEvent.change(screen.getByLabelText("Model ID"), { target: { value: "org/tiny" } });
    fireEvent.click(screen.getByRole("button", { name: "Save base model" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/turned off on this server/i);
    expect(alert.textContent).not.toMatch(/ML_ENABLE_AUTHORING_TOOLS/);
  });

  it("edits a base model and deletes it after confirmation", async () => {
    models = [model];
    render(<BaseModelsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit base model tiny" }));
    fireEvent.change(await screen.findByLabelText("Description"), { target: { value: "Smaller" } });
    fireEvent.click(screen.getByRole("button", { name: "Save base model" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("ml_update_base_model",
      { name: "tiny", model_id: "org/tiny-llama", description: "Smaller", recommended_method: "lora" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete base model tiny" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete base model tiny" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("ml_delete_base_model", { name: "tiny" }));
  });

  it("explains a base model that jobs still use", async () => {
    models = [model];
    render(<BaseModelsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete base model tiny" }));
    callTool.mockImplementation(async (name: string) => {
      if (name === "ml_list_base_models") return ok({ count: 1, models });
      throw typed("base_model_in_use");
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete base model tiny" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/used by a fine-tuning job/i);
  });
});
