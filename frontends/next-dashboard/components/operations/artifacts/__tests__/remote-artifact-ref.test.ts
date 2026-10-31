import { describe, expect, it } from "vitest";
import { parseRemoteArtifactRef, remoteArtifactPath } from "../remote-artifact-ref";

describe("parseRemoteArtifactRef (row 66, feature-map)", () => {
  it("accepts a known provider + safe id (case-normalised)", () => {
    expect(parseRemoteArtifactRef("GDocs", "abc_123-x")).toEqual({ provider: "gdocs", externalId: "abc_123-x" });
  });

  it("rejects an unknown provider", () => {
    expect(parseRemoteArtifactRef("dropbox", "abc")).toBeNull();
  });

  it("rejects an unsafe external id (slash / traversal / spaces)", () => {
    expect(parseRemoteArtifactRef("notion", "a/b")).toBeNull();
    expect(parseRemoteArtifactRef("notion", "../secret")).toBeNull();
    expect(parseRemoteArtifactRef("notion", "a b")).toBeNull();
    expect(parseRemoteArtifactRef("notion", "")).toBeNull();
  });

  it("builds the canonical route", () => {
    const ref = parseRemoteArtifactRef("confluence", "PAGE-42")!;
    expect(remoteArtifactPath(ref)).toBe("/artifacts/remote/confluence/PAGE-42");
  });
});
