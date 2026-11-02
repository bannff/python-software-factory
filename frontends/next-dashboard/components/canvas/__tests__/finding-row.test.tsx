import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Finding } from "@/lib/types";
import { FindingRow } from "../finding-row";
import { kindCounts } from "../finding-kinds";

const base: Finding = {
  id: "f1", severity: "high", title: "Slow tool selection", resource: "unknown", type: "eval",
  description: "", timestamp: 1, source: "graph",
};

describe("FindingRow", () => {
  it("shows title and one muted kind and subject line, without a severity word", () => {
    render(<FindingRow finding={{ ...base, affected_resource_arn: "arn:aws:s3:::bucket/key" }}
      expanded={false} onToggle={vi.fn()} />);
    expect(screen.getByText("Slow tool selection")).toBeTruthy();
    expect(screen.getByText(/^eval · /)).toBeTruthy();
    expect(screen.queryByText("high")).toBeNull();
    expect(screen.getByRole("button").getAttribute("title")).toBe("high");
  });

  it("omits the subject when the finding names none", () => {
    render(<FindingRow finding={base} expanded={false} onToggle={vi.fn()} />);
    expect(screen.getByText("eval")).toBeTruthy();
  });

  it("reports expansion and toggles on click", () => {
    const onToggle = vi.fn();
    render(<FindingRow finding={base} expanded onToggle={onToggle} />);
    const row = screen.getByRole("button");
    expect(row.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(row);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});

describe("kindCounts", () => {
  it("counts distinct kinds, most common first", () => {
    const f = (type: string): Finding => ({ ...base, id: type + Math.random(), type });
    expect(kindCounts([f("eval"), f("vulnerability"), f("eval")])).toEqual([["eval", 2], ["vulnerability", 1]]);
  });
});
