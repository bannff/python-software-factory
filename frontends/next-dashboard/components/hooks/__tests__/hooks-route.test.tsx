import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/components/hooks/hooks-view", () => ({
  default: () => <div data-testid="hooks-manager" />,
}));

import Page from "@/app/(workbench)/hooks/page";

describe("/hooks route", () => {
  it("renders the real hook manager, not a placeholder", () => {
    render(<Page />);
    expect(screen.getByTestId("hooks-manager")).toBeTruthy();
  });
});
