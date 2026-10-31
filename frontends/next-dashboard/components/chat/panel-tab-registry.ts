import type { ChatPanelTab } from "./chat-side-panel";

/**
 * Row 27 (feature-map) — App-contributed panel tabs (`hooks/panelTabRegistry`).
 *
 * Installed apps declare side-panel tabs in `contributes.panelTabs`; each
 * mounts the app's own bundle as the tab body. This is the pure merge model
 * that folds those contributions into the base ChatSidePanel registry
 * (Summary/Pins/Files/Side/Browser): built-in tabs always win an id
 * collision (a contributed tab can never shadow a core tab), contributions
 * are appended in stable order, and duplicate ids among contributions keep
 * the first (earlier-loaded app wins).
 *
 * Pure and self-contained — the caller supplies only ENABLED apps' tabs (no
 * app enabled ⇒ no contributed rows), and the in-process app host that
 * actually mounts each tab body is the deferred backend half.
 */

export interface ContributedTab extends ChatPanelTab {
  /** The app that contributed this tab (for provenance / de-dupe). */
  appId: string;
}

export function mergeContributedTabs(
  base: readonly ChatPanelTab[],
  contributed: readonly ContributedTab[],
): ChatPanelTab[] {
  const seen = new Set(base.map((tab) => tab.id));
  const merged: ChatPanelTab[] = [...base];
  for (const tab of contributed) {
    if (seen.has(tab.id)) continue; // built-in or earlier app already owns this id
    seen.add(tab.id);
    merged.push(tab);
  }
  return merged;
}
