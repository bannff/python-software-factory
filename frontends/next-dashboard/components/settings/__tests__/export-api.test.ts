import { describe, expect, it, vi, beforeEach } from "vitest";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import { previewExport, runExport, previewBundleImport } from "../export-api";

const wrap = (data: unknown) => ({ tool: "t", result: { ok: true, data } });

beforeEach(() => { mocks.callTool.mockReset(); });

describe("export-api", () => {
  it("previewExport parses kind summaries", async () => {
    mocks.callTool.mockResolvedValue(wrap({
      bundle_version: 1, adapter: "companion-x-v1",
      content_digest: `sha256:${"a".repeat(64)}`,
      kinds: [{ kind: "memory", count: 3, excluded: 0, digest: `sha256:${"b".repeat(64)}` }],
    }));
    const preview = await previewExport(["memory"]);
    expect(preview.kinds[0]).toEqual({ kind: "memory", count: 3, excluded: 0, digest: `sha256:${"b".repeat(64)}` });
    expect(mocks.callTool).toHaveBeenCalledWith("portability_export_preview", { kinds: ["memory"] });
  });

  it("runExport parses the written path and byte count", async () => {
    mocks.callTool.mockResolvedValue(wrap({
      path: "/exports/backup.cxbundle.json", bytes_written: 512,
      bundle_version: 1, adapter: "companion-x-v1",
      content_digest: `sha256:${"a".repeat(64)}`, kinds: [],
    }));
    const result = await runExport("backup.cxbundle.json", ["memory"]);
    expect(result.path).toBe("/exports/backup.cxbundle.json");
    expect(result.bytesWritten).toBe(512);
    expect(mocks.callTool).toHaveBeenCalledWith("portability_export", {
      destination_name: "backup.cxbundle.json", kinds: ["memory"],
    });
  });

  it("previewExport throws when the response is missing content_digest", async () => {
    mocks.callTool.mockResolvedValue(wrap({}));
    await expect(previewExport()).rejects.toThrow("Export preview is unavailable.");
  });

  it("previewBundleImport parses reports and disclosed unsupported kinds", async () => {
    mocks.callTool.mockResolvedValue(wrap({
      plan_digest: `sha256:${"a".repeat(64)}`, status: "committed",
      reports: [{ kind: "memory", found: 2, eligible: 2, excluded: 0 }],
      unsupported_kinds: ["kb", "preferences"],
    }));
    const preview = await previewBundleImport("backup.cxbundle.json");
    expect(preview.reports).toEqual([{ kind: "memory", found: 2, eligible: 2, excluded: 0 }]);
    expect(preview.unsupportedKinds).toEqual(["kb", "preferences"]);
    expect(mocks.callTool).toHaveBeenCalledWith("migration_preview_bundle", {
      bundle_ref: "backup.cxbundle.json", kinds: undefined,
    });
  });
});
