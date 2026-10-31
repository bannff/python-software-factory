import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ callTool: vi.fn() }));
import { callTool } from "@/lib/api";
import { EvalsFocusedRun } from "../evals-focused-run";

const mockCall = vi.mocked(callTool);
const response = (data: unknown) => ({ tool: "evals_get_run_result", result: { schema_version: "v1", ok: true, data } });

beforeEach(() => mockCall.mockReset());

describe("focused Evals exact artifact states", () => {
  it("renders loading then an exact found result", async () => {
    mockCall.mockResolvedValue(response({ found: true, result: { verdict: "PASS", total_cases: 1, passed: 1, avg_score: 0.9, case_results: [{ case_name: "exact-case", passed: true, score: 0.9 }] } }) as never);
    render(<EvalsFocusedRun runId="run-exact" onClear={vi.fn()} />);
    expect(screen.getByText(/Loading exact eval artifact/)).toBeTruthy();
    await waitFor(() => expect(screen.getByText("exact-case")).toBeTruthy());
    expect(screen.getByText("1/1")).toBeTruthy();
  });

  it("distinguishes a found artifact with no result fields", async () => {
    mockCall.mockResolvedValue(response({ found: true, result: {} }) as never);
    render(<EvalsFocusedRun runId="run-empty" onClear={vi.fn()} />);
    await waitFor(() => expect(screen.getByText(/artifact is empty/i)).toBeTruthy());
  });

  it("renders found summary data even when no case rows were persisted", async () => {
    mockCall.mockResolvedValue(response({ found: true, result: { verdict: "PASS", total_cases: 2, passed: 2, pass_rate: 1, avg_score: 0.8 } }) as never);
    render(<EvalsFocusedRun runId="run-summary" onClear={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("2/2")).toBeTruthy());
    expect(screen.getByText(/No case rows were persisted/i)).toBeTruthy();
  });

  it("distinguishes a missing artifact", async () => {
    mockCall.mockResolvedValue(response({ found: false, result: null }) as never);
    render(<EvalsFocusedRun runId="run-missing" onClear={vi.fn()} />);
    await waitFor(() => expect(screen.getByText(/No attributable eval artifact/i)).toBeTruthy());
  });

  it("reports API errors as unavailable without aggregate fallback", async () => {
    mockCall.mockResolvedValue({
      tool: "evals_get_run_result",
      result: { schema_version: "v1", ok: false, error: { message: "eval store offline" } },
    } as never);
    render(<EvalsFocusedRun runId="run-error" onClear={vi.fn()} />);
    await waitFor(() => expect(screen.getByText(/Eval artifact unavailable/i)).toBeTruthy());
    expect(screen.getByText("eval store offline")).toBeTruthy();
  });
});
