import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { EvalsRunPanel } from "../evals-run-panel";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });
const EVALUATORS = [
  { name: "helpfulness", description: "Is it helpful", requires_rubric: false },
  { name: "rubric", description: "Custom rubric", requires_rubric: true },
];
let runResponse: () => unknown;
beforeEach(() => {
  callTool.mockReset();
  runResponse = () => ok({ run_id: "r1", name: "smoke", case_results: [{}, {}], summary: { overall_score: 0.9, pass_rate: 1, total_cases: 2, evaluation_errors: 0 }, evaluators_used: ["helpfulness"] });
  callTool.mockImplementation(async (name: string) => {
    if (name === "evals_list_evaluators") return ok({ evaluators: EVALUATORS });
    return runResponse();
  });
});

const open = async () => { fireEvent.click(await screen.findByRole("button", { name: "Run an eval" })); await screen.findByLabelText("Prompt 1"); };
const prompt = (text = "What is 2+2?") => fireEvent.change(screen.getByLabelText("Prompt 1"), { target: { value: text } });

describe("EvalsRunPanel", () => {
  it("lists the evaluators the server offers", async () => {
    render(<EvalsRunPanel />);
    await open();
    expect(await screen.findByLabelText("helpfulness")).toBeTruthy();
  });

  it("asks for a prompt and an evaluator before running", async () => {
    render(<EvalsRunPanel />);
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Start run" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/prompt/i);
    prompt();
    fireEvent.click(screen.getByRole("button", { name: "Start run" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/evaluator/i);
    expect(callTool).not.toHaveBeenCalledWith("evals_run_experiment", expect.anything());
  });

  it("shows the rubric field only for evaluators that need one", async () => {
    render(<EvalsRunPanel />);
    await open();
    expect(screen.queryByLabelText("Rubric")).toBeNull();
    fireEvent.click(await screen.findByLabelText("rubric"));
    expect(screen.getByLabelText("Rubric")).toBeTruthy();
  });

  it("runs the chosen cases and evaluators and reports the result", async () => {
    render(<EvalsRunPanel />);
    await open();
    prompt();
    fireEvent.change(screen.getByLabelText("Expected answer 1"), { target: { value: "4" } });
    fireEvent.click(await screen.findByLabelText("helpfulness"));
    fireEvent.change(screen.getByLabelText("Run name"), { target: { value: "smoke" } });
    fireEvent.click(screen.getByRole("button", { name: "Start run" }));
    const line = (await screen.findByRole("status")).textContent ?? "";
    expect(line).toMatch(/2 cases · overall score 0\.90 · pass rate 100%/);
    expect(line).not.toMatch(/error|could not be scored/i);
    expect(callTool).toHaveBeenCalledWith("evals_run_experiment", {
      cases: [{ input: "What is 2+2?", expected_output: "4" }], evaluator_names: ["helpfulness"], experiment_name: "smoke",
    });
  });

  it("says case in the singular and reports unscored rows only when there are some", async () => {
    runResponse = () => ok({ run_id: "r2", case_results: [{}], summary: { overall_score: 0.5, pass_rate: 0.5, evaluation_errors: 1 } });
    render(<EvalsRunPanel />);
    await open();
    prompt();
    fireEvent.click(await screen.findByLabelText("helpfulness"));
    fireEvent.click(screen.getByRole("button", { name: "Start run" }));
    const line = (await screen.findByRole("status")).textContent ?? "";
    expect(line).toMatch(/1 case · /);
    expect(line).toMatch(/1 could not be scored/);
  });

  it("adds and removes cases", async () => {
    render(<EvalsRunPanel />);
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Add case" }));
    expect(screen.getByLabelText("Prompt 2")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove case 2" }));
    expect(screen.queryByLabelText("Prompt 2")).toBeNull();
  });

  it("explains an opaque failure as missing evaluation models, without raw codes", async () => {
    runResponse = () => ({ schema_version: "v1", ok: false, error: "tool_execution_failed" });
    render(<EvalsRunPanel />);
    await open();
    prompt();
    fireEvent.click(await screen.findByLabelText("helpfulness"));
    fireEvent.click(screen.getByRole("button", { name: "Start run" }));
    const alert = await screen.findByRole("alert");
    await waitFor(() => expect(alert.textContent).toMatch(/evaluation models/i));
    expect(alert.textContent).not.toContain("tool_execution_failed");
  });

  it("maps the typed model-unavailable code to the same friendly message", async () => {
    runResponse = () => ({ schema_version: "v1", ok: false, error: "eval_model_unavailable" });
    render(<EvalsRunPanel />);
    await open();
    prompt();
    fireEvent.click(await screen.findByLabelText("helpfulness"));
    fireEvent.click(screen.getByRole("button", { name: "Start run" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/evaluation models/i);
  });
});
