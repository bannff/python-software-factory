import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { TrainPanel } from "../train-panel";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
let types: string[] | undefined;
beforeEach(() => {
  callTool.mockReset(); types = ["lightgbm", "tcn"];
  callTool.mockImplementation(async (name: string) => {
    if (name === "ml_get_capabilities") return ok(types ? { name: "machine_learning", timeseries_model_types: types } : { name: "machine_learning" });
    if (name === "ml_list_datasets") return ok({ count: 1, datasets: [{ dataset_id: "d1", uri: "s3://bucket/X.npy", manifest_uri: "s3://m", digest: "sha256:" + "a".repeat(64), view_name: "v", view_schema_version: "1", description: "", revision: 1 }] });
    return ok({ job_id: "job-9", model_type: "tcn", status: "completed", metrics: { accuracy: 0.91 } });
  });
});

const open = async () => { fireEvent.click(await screen.findByRole("button", { name: "Train a model" })); await screen.findByLabelText("Features (X)"); };
const fill = (x = "s3://bucket/X.npy", y = "s3://bucket/y.npy") => {
  fireEvent.change(screen.getByLabelText("Features (X)"), { target: { value: x } });
  fireEvent.change(screen.getByLabelText("Labels (y)"), { target: { value: y } });
};

describe("TrainPanel", () => {
  it("explains the two inputs in plain words", async () => {
    render(<TrainPanel />);
    await open();
    expect(screen.getByText(/windowed feature array/i)).toBeTruthy();
    expect(screen.getByText(/one label per window/i)).toBeTruthy();
  });

  it("offers the model types the server reports", async () => {
    render(<TrainPanel />);
    await open();
    expect(await screen.findByRole("option", { name: "tcn" })).toBeTruthy();
  });

  it("falls back to a text field when the server lists no model types", async () => {
    types = undefined;
    render(<TrainPanel />);
    await open();
    expect(screen.getByLabelText("Model type").tagName).toBe("INPUT");
  });

  it("requires both locations before sending anything", async () => {
    render(<TrainPanel />);
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Start training" }));
    expect((await screen.findAllByRole("alert")).length).toBeGreaterThan(0);
    expect(callTool).not.toHaveBeenCalledWith("ml_train_timeseries", expect.anything());
  });

  it("starts training and reports the result", async () => {
    render(<TrainPanel />);
    await open();
    await screen.findByRole("option", { name: "tcn" });
    fireEvent.change(screen.getByLabelText("Model type"), { target: { value: "tcn" } });
    fill();
    fireEvent.change(screen.getByLabelText("Experiment name"), { target: { value: "first run" } });
    fireEvent.click(screen.getByRole("button", { name: "Start training" }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("ml_train_timeseries",
      { model_type: "tcn", X_uri: "s3://bucket/X.npy", y_uri: "s3://bucket/y.npy", experiment_name: "first run" }));
    expect((await screen.findByRole("status")).textContent).toMatch(/completed/i);
    expect(screen.getByRole("status").textContent).toMatch(/accuracy/i);
  });

  it("turns the backend's leaky and opaque errors into plain sentences", async () => {
    render(<TrainPanel />);
    await open();
    await screen.findByRole("option", { name: "tcn" });
    fireEvent.change(screen.getByLabelText("Model type"), { target: { value: "tcn" } });
    fill("/tmp/x.npy", "/tmp/y.npy");
    callTool.mockImplementation(async (name: string) => {
      if (name === "ml_train_timeseries") throw new Error("tool_execution_failed");
      return ok({});
    });
    fireEvent.click(screen.getByRole("button", { name: "Start training" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/could not run on the server/i);
    expect(alert.textContent).toMatch(/server log/i);
    expect(alert.textContent).not.toMatch(/tool_execution_failed/);
    expect(alert.textContent).not.toMatch(/dataset locations exist/i);
  });

  it.each([
    ["timeseries_model_type_invalid", /model type isn't available/i],
    ["timeseries_config_invalid", /training settings/i],
    ["training_data_unreadable", /locations exist and can be read/i],
    ["training_failed", /training failed/i],
    ["training_data_shape_invalid", /wrong shape/i],
    ["model_root_not_configured", /no folder/i],
    ["symlink_path_rejected", /real path/i],
    ["native_dependency_missing", /training packages/i],
  ])("maps the typed code %s to a plain sentence", async (code, expected) => {
    render(<TrainPanel />);
    await open();
    await screen.findByRole("option", { name: "tcn" });
    fireEvent.change(screen.getByLabelText("Model type"), { target: { value: "tcn" } });
    fill();
    callTool.mockImplementation(async (name: string) => {
      if (name === "ml_train_timeseries") throw Object.assign(new Error(code), { reason: code });
      return ok({});
    });
    fireEvent.click(screen.getByRole("button", { name: "Start training" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(expected);
    expect(alert.textContent).not.toContain(code);
  });
});
