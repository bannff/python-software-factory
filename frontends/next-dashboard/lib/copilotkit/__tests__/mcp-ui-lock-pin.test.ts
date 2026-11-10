import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * `@mcp-ui/client` must stay on the verified pin (#11). A bump to 7.x broke the
 * export shape before (the 5.6.2 -> 7.1.1 incident); this fails the PR that
 * changes package.json or the lockfile, before anyone boots the dashboard.
 * To move the pin deliberately, update VERIFIED_PIN after checking
 * `mcp-ui-sdk-presence.test.ts` and the React runtime guard (#47).
 */
const VERIFIED_PIN = "5.6.2";
const ROOT = path.resolve(__dirname, "..", "..", "..");
const read = (file: string) => JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));

describe("@mcp-ui/client pin", () => {
  it("package.json declares the exact verified version", () => {
    expect(read("package.json").dependencies["@mcp-ui/client"]).toBe(VERIFIED_PIN);
  });

  it("the lockfile resolves the same version", () => {
    const entry = read("package-lock.json").packages["node_modules/@mcp-ui/client"];
    expect(entry.version).toBe(VERIFIED_PIN);
  });
});
