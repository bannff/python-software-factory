import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  prefs: {
    plainDiffs: false, hiddenModels: [] as string[], defaultMemoryMode: "persistent" as const,
    collapseMessageInput: false, pinLatestPrompt: false, revision: 2,
  },
  update: vi.fn(), announce: vi.fn(), refresh: vi.fn(),
}));
vi.mock("@/components/settings/use-chat-preferences", () => ({
  useChatPreferences: () => ({ preferences: mocks.prefs, loading: false, error: null, refresh: mocks.refresh }),
  announceChatPreferences: (...args: unknown[]) => mocks.announce(...args),
}));
vi.mock("@/components/settings/chat-preferences-api", () => ({
  updateChatPreferences: (...args: unknown[]) => mocks.update(...args),
}));
vi.mock("@/lib/hooks/use-model-catalog", () => ({ useModelCatalog: () => ({
  loading: false, error: null, models: [], refresh: vi.fn(), groups: [
    { provider: "openrouter", models: [{ model_id: "openrouter/a", model: "a", provider: "openrouter" }] },
  ],
}) }));

import ChatPreferencesPanel from "../chat-preferences-panel";

beforeEach(() => {
  mocks.prefs.plainDiffs = false; mocks.prefs.hiddenModels = [];
  mocks.prefs.defaultMemoryMode = "persistent"; mocks.prefs.collapseMessageInput = false;
  mocks.prefs.pinLatestPrompt = false;
  mocks.update.mockReset().mockImplementation(async (value) => ({ ...value, revision: value.revision + 1 }));
  mocks.announce.mockReset(); mocks.refresh.mockReset();
});

describe("ChatPreferencesPanel", () => {
  it("persists plain diff mode with revision fencing", async () => {
    render(<ChatPreferencesPanel />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Plain diffs" }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({
      plainDiffs: true, hiddenModels: [], defaultMemoryMode: "persistent",
      collapseMessageInput: false, pinLatestPrompt: false, revision: 2,
    }));
    expect(mocks.announce).toHaveBeenCalledWith({
      plainDiffs: true, hiddenModels: [], defaultMemoryMode: "persistent",
      collapseMessageInput: false, pinLatestPrompt: false, revision: 3,
    });
  });

  it("hides a configured model without deleting it", async () => {
    render(<ChatPreferencesPanel />);
    fireEvent.click(screen.getByRole("checkbox", { name: "a" }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({
      plainDiffs: false, hiddenModels: ["openrouter/a"], defaultMemoryMode: "persistent",
      collapseMessageInput: false, pinLatestPrompt: false, revision: 2,
    }));
    expect(screen.getByText(/stay configured/)).toBeTruthy();
  });

  it("changes the default memory mode for new dashboard-created chats", async () => {
    render(<ChatPreferencesPanel />);
    expect(screen.getByRole("radio", { name: "Persistent" })).toHaveProperty("checked", true);
    expect(screen.getByRole("radio", { name: "Incognito" })).toHaveProperty("checked", false);
    fireEvent.click(screen.getByRole("radio", { name: "Incognito" }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({
      plainDiffs: false, hiddenModels: [], defaultMemoryMode: "incognito",
      collapseMessageInput: false, pinLatestPrompt: false, revision: 2,
    }));
    expect(mocks.announce).toHaveBeenCalledWith({
      plainDiffs: false, hiddenModels: [], defaultMemoryMode: "incognito",
      collapseMessageInput: false, pinLatestPrompt: false, revision: 3,
    });
  });

  it("row 12 (feature-map): toggles collapse the message input, off by default", async () => {
    render(<ChatPreferencesPanel />);
    const toggle = screen.getByRole("checkbox", { name: "Collapse the message input" });
    expect(toggle).toHaveProperty("checked", false);
    fireEvent.click(toggle);
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({
      plainDiffs: false, hiddenModels: [], defaultMemoryMode: "persistent",
      collapseMessageInput: true, pinLatestPrompt: false, revision: 2,
    }));
    expect(mocks.announce).toHaveBeenCalledWith({
      plainDiffs: false, hiddenModels: [], defaultMemoryMode: "persistent",
      collapseMessageInput: true, pinLatestPrompt: false, revision: 3,
    });
  });

  it("row 10 (feature-map): toggles pin the latest turn, off by default", async () => {
    render(<ChatPreferencesPanel />);
    const toggle = screen.getByRole("checkbox", { name: "Pin the latest turn" });
    expect(toggle).toHaveProperty("checked", false);
    fireEvent.click(toggle);
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({
      plainDiffs: false, hiddenModels: [], defaultMemoryMode: "persistent",
      collapseMessageInput: false, pinLatestPrompt: true, revision: 2,
    }));
    expect(mocks.announce).toHaveBeenCalledWith({
      plainDiffs: false, hiddenModels: [], defaultMemoryMode: "persistent",
      collapseMessageInput: false, pinLatestPrompt: true, revision: 3,
    });
  });
});
