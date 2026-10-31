import { describe, expect, it } from "vitest";
import {
  buildInsertion, commonPrefix, completionMode, extractToken, foldersOnly,
  isCommandToken, isSafeName, readWord, unescapeWord,
} from "../terminal-completion";

describe("terminal completion rules", () => {
  it("extracts escaped path words at the cursor", () => {
    const line = "$ cd my\\ dir/do";
    expect(extractToken(line, line.length)).toEqual({ token: "my\\ dir/do", start: 5 });
    expect(unescapeWord("my\\ dir/do")).toBe("my dir/do");
    expect(readWord(line, line.length)?.command).toBe("cd");
  });

  it("refuses quoted, incomplete escaped, and mid-word input", () => {
    expect(readWord("$ cd 'my", 8)).toBeNull();
    expect(readWord("$ cd my\\", 8)).toBeNull();
    expect(readWord("$ cd docs", 7)).toBeNull();
  });

  it("selects disjoint path and command tiers", () => {
    expect(completionMode("../do", "cd")).toBe("path");
    expect(completionMode("do", "cd")).toBe("path");
    expect(completionMode("cre", "gh")).toBe("command");
    expect(completionMode("gh", "")).toBe("none");
    expect(foldersOnly("cd")).toBe(true);
    expect(foldersOnly("ls")).toBe(false);
  });

  it("escapes path insertion and guards option-shaped filenames", () => {
    expect(buildInsertion("my", "my dir", "/")).toEqual({ erase: 0, text: "\\ dir/" });
    expect(buildInsertion("-f", "-force", " ")).toEqual({ erase: 2, text: "./-force " });
    expect(buildInsertion("cre", "create", " ", false)).toEqual({ erase: 0, text: "ate " });
  });

  it("computes Unicode-safe common prefixes and validates offered tokens", () => {
    expect(commonPrefix(["docs", "docsite"])).toBe("docs");
    expect(isSafeName("evil\ncommand")).toBe(false);
    expect(isCommandToken("--force", true)).toBe(true);
    expect(isCommandToken("bad flag", true)).toBe(false);
  });
});
