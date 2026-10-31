import { describe, expect, it } from "vitest";
import { mergeContributedTabs, type ContributedTab } from "../panel-tab-registry";
import type { ChatPanelTab } from "../chat-side-panel";

const tab = (id: string): ChatPanelTab => ({ id, label: id, render: () => null });
const appTab = (id: string, appId: string): ContributedTab => ({ ...tab(id), appId });

const BASE = [tab("summary"), tab("side"), tab("browser")];

describe("mergeContributedTabs (row 27, feature-map)", () => {
  it("appends contributed tabs after the base tabs in order", () => {
    const merged = mergeContributedTabs(BASE, [appTab("notes", "app-a"), appTab("kanban", "app-b")]);
    expect(merged.map((t) => t.id)).toEqual(["summary", "side", "browser", "notes", "kanban"]);
  });

  it("never lets a contributed tab shadow a built-in id", () => {
    const merged = mergeContributedTabs(BASE, [appTab("browser", "evil-app"), appTab("notes", "app-a")]);
    expect(merged.map((t) => t.id)).toEqual(["summary", "side", "browser", "notes"]);
    // the surviving "browser" is the built-in, not the app's
    expect((merged.find((t) => t.id === "browser") as ContributedTab).appId).toBeUndefined();
  });

  it("keeps the first contribution on a duplicate id (earlier app wins)", () => {
    const merged = mergeContributedTabs(BASE, [appTab("notes", "app-a"), appTab("notes", "app-b")]);
    expect(merged.filter((t) => t.id === "notes")).toHaveLength(1);
    expect((merged.find((t) => t.id === "notes") as ContributedTab).appId).toBe("app-a");
  });

  it("returns the base unchanged when no app contributes", () => {
    expect(mergeContributedTabs(BASE, []).map((t) => t.id)).toEqual(["summary", "side", "browser"]);
  });
});
