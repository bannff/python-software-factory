import { describe, expect, it, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ useAgentContext: vi.fn(), callTool: vi.fn(), useToolData: vi.fn() }));
vi.mock("@copilotkit/react-core/v2", () => ({ useAgentContext: (...args: unknown[]) => mocks.useAgentContext(...args) }));
vi.mock("@companion-x/shared-renderer", () => ({ useToolData: (...args: unknown[]) => mocks.useToolData(...args) }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import { ArtifactDetail } from "../artifact-detail";
import type { Artifact } from "../artifact-types";

const artifact: Artifact = {
  slug: "release-notes", name: "Release Notes", description: "Weekly summary",
  tags: [], kind: "markdown", content: "# Hello\nBody text", version: 2, revision: 2,
  updated_at: "2026-09-15T00:00:00Z", folder_id: null,
};

beforeEach(() => {
  mocks.useAgentContext.mockReset();
  mocks.callTool.mockReset();
  mocks.useToolData.mockReset().mockReturnValue({ data: {}, refetch: vi.fn() });
});

describe("ArtifactDetail companion-chat context (feature-map row 64)", () => {
  it("publishes the open artifact into the global chat agent's context, not a duplicate chat surface", () => {
    render(<ArtifactDetail artifact={artifact} onClose={vi.fn()} onChanged={vi.fn()} />);
    expect(mocks.useAgentContext).toHaveBeenCalledTimes(1);
    const call = mocks.useAgentContext.mock.calls[0][0] as { description: string; value: Record<string, unknown> };
    expect(call.description).toContain("artifacts_update");
    expect(call.value).toMatchObject({
      slug: "release-notes", name: "Release Notes", kind: "markdown", version: 2,
    });
    expect(call.value.content).toBe("# Hello\nBody text");
  });

  it("truncates very large artifact content before publishing, rather than ballooning every chat turn", () => {
    const big = { ...artifact, content: "x".repeat(5_000) };
    render(<ArtifactDetail artifact={big} onClose={vi.fn()} onChanged={vi.fn()} />);
    const call = mocks.useAgentContext.mock.calls[0][0] as { value: Record<string, unknown> };
    expect((call.value.content as string).length).toBeLessThan(5_000);
    expect(call.value.content as string).toContain("(truncated)");
  });

  it("re-publishes when the artifact changes (e.g. after a revert)", () => {
    const { rerender } = render(<ArtifactDetail artifact={artifact} onClose={vi.fn()} onChanged={vi.fn()} />);
    const next = { ...artifact, revision: 3, version: 3, content: "# Hello\nUpdated body" };
    rerender(<ArtifactDetail artifact={next} onClose={vi.fn()} onChanged={vi.fn()} />);
    const lastCall = mocks.useAgentContext.mock.calls.at(-1)?.[0] as { value: Record<string, unknown> };
    expect(lastCall.value.version).toBe(3);
    expect(lastCall.value.content).toBe("# Hello\nUpdated body");
  });
});
