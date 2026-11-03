import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { DatasetsPanel } from "../datasets-panel";
import { validateDatasetForm } from "../dataset-validation";

const DIGEST = "sha256:" + "a".repeat(64);
const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
const row = { dataset_id: "chat-v1", uri: "s3://d/chat.jsonl", manifest_uri: "s3://d/m.json", digest: DIGEST,
  view_name: "chat", view_schema_version: "1", description: "Chat set", revision: 2 };
let rows: unknown[] = [];
const typed = (code: string) => Object.assign(new Error(code), { reason: code });

beforeEach(() => {
  callTool.mockReset(); rows = [];
  callTool.mockImplementation(async (name: string) => {
    if (name === "ml_list_datasets") return ok({ count: rows.length, datasets: rows });
    return ok({ dataset: row, dataset_id: "chat-v1", deleted: true });
  });
});

describe("validateDatasetForm", () => {
  const form = { name: "chat-v1", uri: "s3://d", manifest_uri: "s3://m", digest: DIGEST, view_name: "chat", view_schema_version: "1", description: "" };
  it("accepts a valid form", () => expect(validateDatasetForm(form)).toEqual({}));
  it("requires the prefixed digest", () => {
    expect(validateDatasetForm({ ...form, digest: "a".repeat(64) }).digest).toMatch(/sha256:/);
  });
  it("checks the name pattern and URI schemes", () => {
    const errs = validateDatasetForm({ ...form, name: "Bad Name", uri: "/tmp/x", manifest_uri: "" });
    expect(Object.keys(errs).sort()).toEqual(["manifest_uri", "name", "uri"]);
  });
});

describe("DatasetsPanel", () => {
  it("offers a first dataset when there are none", async () => {
    render(<DatasetsPanel />);
    expect(await screen.findByText("No datasets registered yet")).toBeTruthy();
  });

  it("registers a dataset with the server's field names", async () => {
    render(<DatasetsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Register dataset" }));
    for (const [label, value] of [["Name", "chat-v1"], ["URI", "s3://d/chat.jsonl"], ["Manifest URI", "s3://d/m.json"],
      ["Digest", DIGEST], ["View name", "chat"], ["View schema version", "1"]]) {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    }
    fireEvent.click(screen.getByRole("button", { name: "Save dataset" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("ml_register_dataset", {
      name: "chat-v1", uri: "s3://d/chat.jsonl", manifest_uri: "s3://d/m.json", digest: DIGEST,
      view_name: "chat", view_schema_version: "1", description: "" }));
  });

  it("puts a digest mismatch and a duplicate name on their fields", async () => {
    render(<DatasetsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Register dataset" }));
    for (const [label, value] of [["Name", "chat-v1"], ["URI", "s3://d"], ["Manifest URI", "s3://m"],
      ["Digest", DIGEST], ["View name", "chat"], ["View schema version", "1"]]) {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    }
    callTool.mockImplementation(async (name: string) => {
      if (name === "ml_list_datasets") return ok({ count: 0, datasets: [] });
      throw typed("dataset_digest_mismatch");
    });
    fireEvent.click(screen.getByRole("button", { name: "Save dataset" }));
    expect(await screen.findByText(/does not match/i)).toBeTruthy();
  });

  it("edits the description with the expected revision and deletes after confirmation", async () => {
    rows = [row];
    render(<DatasetsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit dataset chat-v1" }));
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Better" } });
    fireEvent.click(screen.getByRole("button", { name: "Save description" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("ml_update_dataset",
      { dataset_id: "chat-v1", description: "Better", expected_revision: 2 }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete dataset chat-v1" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete dataset chat-v1" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("ml_delete_dataset", { dataset_id: "chat-v1" }));
  });

  it("explains a dataset that is still in use", async () => {
    rows = [row];
    render(<DatasetsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete dataset chat-v1" }));
    callTool.mockImplementation(async (name: string) => {
      if (name === "ml_list_datasets") return ok({ count: 1, datasets: rows });
      throw typed("dataset_in_use");
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete dataset chat-v1" }));
    expect(await screen.findByText(/used by a fine-tuning job/i)).toBeTruthy();
  });
});
