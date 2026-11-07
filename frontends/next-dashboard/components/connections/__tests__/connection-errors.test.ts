import { describe, expect, it } from "vitest";
import { connectionFailure } from "../connection-errors";

describe("connectionFailure", () => {
  it("words typed backend codes", () => {
    expect(connectionFailure("Couldn’t add server.", new Error("connections_document_invalid")))
      .toBe("Couldn’t add server. That isn’t a valid mcpServers JSON document.");
    expect(connectionFailure("Couldn’t add server.", new Error("connections_revision_conflict")))
      .toContain("changed");
  });

  it("keeps the server reason for codes it does not know", () => {
    expect(connectionFailure("Couldn’t add server.", new Error("boom"))).toBe("Couldn’t add server. (boom)");
    expect(connectionFailure("Couldn’t add server.", "x")).toBe("Couldn’t add server.");
  });
});
