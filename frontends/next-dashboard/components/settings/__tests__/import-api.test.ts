import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ call: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: mocks.call }));

import { getMigration, previewMigration, startMigration } from "../import-api";

const response = (data: unknown) => ({ tool: "migration", result: { ok: true, data } });

beforeEach(() => { mocks.call.mockReset(); });

describe("Migration Settings API", () => {
  it("previews selected kinds through the strict merge-only source", async () => {
    mocks.call.mockResolvedValue(response({
      plan_digest: `sha256:${"a".repeat(64)}`, status: "planned",
      reports: [{ kind: "lessons", found: 3, eligible: 2, excluded: 1 }],
      samples: [{ kind: "lessons", sample: "Keep evidence" }],
    }));
    await expect(previewMigration(["lessons"])).resolves.toEqual({
      planDigest: `sha256:${"a".repeat(64)}`, status: "planned",
      reports: [{ kind: "lessons", found: 3, eligible: 2, excluded: 1 }],
      samples: [{ kind: "lessons", sample: "Keep evidence" }],
    });
    expect(mocks.call).toHaveBeenCalledWith("migration_preview", {
      source: "kirocrew-v1", kinds: ["lessons"],
    });
  });

  it("starts only the immutable preview plan and selected kinds", async () => {
    mocks.call.mockResolvedValue(response({ run_id: "run-1", status: "running" }));
    const preview = { planDigest: `sha256:${"b".repeat(64)}`, status: "planned", reports: [], samples: [] };
    await expect(startMigration(preview, ["memory", "lessons"])).resolves.toEqual({
      runId: "run-1", status: "running", progress: [], terminalReason: "",
    });
    expect(mocks.call).toHaveBeenCalledWith("migration_start", {
      plan_digest: preview.planDigest, kinds: ["memory", "lessons"], source: "kirocrew-v1",
    });
  });

  it("reads typed per-kind progress without exposing source records", async () => {
    mocks.call.mockResolvedValue(response({
      run_id: "run-1", status: "succeeded", terminal_reason: "completed",
      progress: [{ kind: "memory", imported: 4, skipped: 1, failed: 0, cursor: 5 }],
    }));
    await expect(getMigration("run-1")).resolves.toEqual({
      runId: "run-1", status: "succeeded", terminalReason: "completed",
      progress: [{ kind: "memory", imported: 4, skipped: 1, failed: 0, cursor: 5 }],
    });
    expect(mocks.call).toHaveBeenCalledWith("migration_get", { run_id: "run-1" });
  });
});
