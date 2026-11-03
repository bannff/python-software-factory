import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { FineTunePanel } from "../finetune-panel";
import { validateJobForm } from "../finetune-validation";

const DIGEST = "a".repeat(64);
const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
const methods = ok({ methods: [{ name: "lora", description: "Low-Rank Adaptation" }, { name: "ia3", description: "IA3" }] });
const job = (id: string, status: string) => ({ id, status, method: "lora", base_model: "llama-3", loss: 0.42, checkpoints: 2 });
let jobs: unknown[] = [];
const typed = (code: string) => Object.assign(new Error(code), { reason: code });

beforeEach(() => {
  callTool.mockReset(); jobs = [];
  callTool.mockImplementation(async (name: string) => {
    if (name === "ml_list_finetuning_jobs") return ok({ count: jobs.length, jobs });
    if (name === "ml_list_finetuning_methods") return methods;
    return ok({ id: "job-1", status: "pending" });
  });
});

describe("validateJobForm", () => {
  const form = { method: "lora", base_model: "llama-3", dataset_uri: "s3://d", manifest_uri: "s3://m", dataset_digest: DIGEST, view_name: "chat", view_schema_version: "1" };
  it("accepts a complete form", () => expect(validateJobForm(form)).toEqual({}));
  it("requires a SHA-256 hex digest, not a prefixed or short one", () => {
    expect(validateJobForm({ ...form, dataset_digest: "sha256:" + DIGEST }).dataset_digest).toMatch(/64/);
    expect(validateJobForm({ ...form, dataset_digest: "abc" }).dataset_digest).toMatch(/64/);
  });
  it("requires URIs with a scheme", () => {
    const errs = validateJobForm({ ...form, dataset_uri: "/tmp/data.jsonl", manifest_uri: "relative/path" });
    expect(Object.keys(errs).sort()).toEqual(["dataset_uri", "manifest_uri"]);
  });
  it("requires every dataset field", () => {
    const errs = validateJobForm({ ...form, dataset_uri: "", dataset_digest: " " });
    expect(Object.keys(errs).sort()).toEqual(["dataset_digest", "dataset_uri"]);
  });
});

describe("FineTunePanel", () => {
  it("offers a first job when there are none", async () => {
    render(<FineTunePanel />);
    expect(await screen.findByText("No fine-tuning jobs yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "New job" })).toBeTruthy();
  });

  it("starts a pending job and stops a running one", async () => {
    jobs = [job("job-a", "pending"), job("job-b", "running")];
    render(<FineTunePanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Start job job-a" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("ml_start_finetuning_job", { job_id: "job-a" }));
    fireEvent.click(screen.getByRole("button", { name: "Stop job job-b" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("ml_stop_finetuning_job", { job_id: "job-b" }));
    expect(screen.queryByRole("button", { name: "Start job job-b" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Stop job job-a" })).toBeNull();
  });

  it("creates a job from the form with the chosen method", async () => {
    render(<FineTunePanel />);
    fireEvent.click(await screen.findByRole("button", { name: "New job" }));
    await screen.findByRole("option", { name: "ia3" });
    fireEvent.change(screen.getByLabelText("Method"), { target: { value: "ia3" } });
    for (const [label, value] of [["Base model", "llama-3"], ["Dataset URI", "s3://d"], ["Manifest URI", "s3://m"],
      ["Dataset digest", DIGEST], ["View name", "chat"], ["View schema version", "1"]]) {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    }
    fireEvent.click(screen.getByRole("button", { name: "Create job" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("ml_create_finetuning_job", {
      method: "ia3", base_model: "llama-3", dataset_uri: "s3://d", manifest_uri: "s3://m",
      dataset_digest: DIGEST, view_name: "chat", view_schema_version: "1" }));
  });

  it("creates a job from a registered dataset, sending only its id", async () => {
    const dsRow = { dataset_id: "chat-v1", uri: "s3://d", manifest_uri: "s3://m", digest: "sha256:" + DIGEST, view_name: "chat", view_schema_version: "1", description: "", revision: 1 };
    callTool.mockImplementation(async (name: string) => {
      if (name === "ml_list_finetuning_jobs") return ok({ count: 0, jobs: [] });
      if (name === "ml_list_finetuning_methods") return methods;
      if (name === "ml_list_datasets") return ok({ count: 1, datasets: [dsRow] });
      return ok({ id: "job-1", status: "pending" });
    });
    render(<FineTunePanel />);
    fireEvent.click(await screen.findByRole("button", { name: "New job" }));
    await screen.findByRole("option", { name: "chat-v1" });
    fireEvent.change(screen.getByLabelText("Dataset"), { target: { value: "chat-v1" } });
    fireEvent.change(screen.getByLabelText("Base model"), { target: { value: "llama-3" } });
    expect(screen.queryByLabelText("Dataset URI")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Create job" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("ml_create_finetuning_job",
      { method: "lora", base_model: "llama-3", dataset_id: "chat-v1" }));
  });

  it("shows empty dataset fields before sending anything", async () => {
    render(<FineTunePanel />);
    fireEvent.click(await screen.findByRole("button", { name: "New job" }));
    fireEvent.click(await screen.findByRole("button", { name: "Create job" }));
    expect((await screen.findAllByRole("alert")).length).toBeGreaterThan(0);
    expect(callTool).not.toHaveBeenCalledWith("ml_create_finetuning_job", expect.anything());
  });

  it("surfaces the server's reason when a job action fails", async () => {
    jobs = [job("job-a", "pending")];
    callTool.mockImplementation(async (name: string) => {
      if (name === "ml_list_finetuning_jobs") return ok({ count: 1, jobs });
      if (name === "ml_list_finetuning_methods") return methods;
      throw typed("job_not_startable");
    });
    render(<FineTunePanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Start job job-a" }));
    expect(await screen.findByText(/job_not_startable/)).toBeTruthy();
  });
});
