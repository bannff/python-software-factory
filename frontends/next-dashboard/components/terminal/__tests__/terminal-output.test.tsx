import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TerminalOutput } from "../terminal-output";

const DIFF = "@@ -1 +1 @@\n-old\n+new";

describe("TerminalOutput", () => {
  it("highlights diff lines by default", () => {
    const { container } = render(<TerminalOutput output={DIFF} plain={false} />);
    expect(container.querySelector(".text-violet-300")?.textContent).toContain("@@");
    expect(container.querySelector(".text-rose-300")?.textContent).toContain("-old");
    expect(container.querySelector(".text-emerald-300")?.textContent).toContain("+new");
  });

  it("renders one plain text node when plain diffs are enabled", () => {
    const { container } = render(<TerminalOutput output={DIFF} plain />);
    expect(container.textContent).toBe(DIFF);
    expect(container.querySelector("span")).toBeNull();
  });
});
