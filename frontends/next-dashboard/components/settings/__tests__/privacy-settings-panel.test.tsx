import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => mocks.callTool(...a) }));

import PrivacySettingsPanel from "../privacy-settings-panel";

const ok = (data: Record<string, unknown>) => ({ structuredContent: { ok: true, data } });

beforeEach(() => { mocks.callTool.mockReset(); });

describe("Settings → Privacy", () => {
  it("shows the real collection status, matching the disclosure text", async () => {
    mocks.callTool.mockResolvedValueOnce(ok({ collecting: true, sample_rate: 1, redacted_field_names: [],
      raw_retention_days: 7, rollup_retention_days: 365, configurable: true }));
    render(<PrivacySettingsPanel />);
    expect(await screen.findByText("100%")).toBeTruthy();
    expect(screen.getByText("none")).toBeTruthy();
    expect(screen.getByText("7 days")).toBeTruthy();
    expect(screen.getByText(/operator sets these via environment variables/)).toBeTruthy();
  });

  it("shows configured sampling and redacted field names when the operator set them", async () => {
    mocks.callTool.mockResolvedValueOnce(ok({ collecting: true, sample_rate: 0.25, redacted_field_names: ["email", "ssn"],
      raw_retention_days: 3, rollup_retention_days: 90, configurable: true }));
    render(<PrivacySettingsPanel />);
    expect(await screen.findByText("25%")).toBeTruthy();
    expect(screen.getByText("email, ssn")).toBeTruthy();
  });

  it("degrades to an explicit error when the tool call fails", async () => {
    mocks.callTool.mockRejectedValueOnce(new Error("boom"));
    render(<PrivacySettingsPanel />);
    expect((await screen.findByRole("alert")).textContent).toBe("Collection status unavailable.");
  });
});
