import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BridgeAdapterProvider, type BridgeAdapter } from "../index";
import { ItemListRenderer } from "../renderers/renderers-item-list";

const node = (props: Record<string, unknown>) => ({
  id: "n", component: "item_list", originalType: "item_list",
  props: { data_tool: "evals_list", data_path: "items", empty_message: "No experiments yet.", ...props },
});

const mount = (adapter: BridgeAdapter, props: Record<string, unknown>) =>
  render(
    <BridgeAdapterProvider adapter={adapter}>
      <ItemListRenderer node={node(props)} renderChildren={() => null} />
    </BridgeAdapterProvider>,
  );

describe("ItemList empty_action", () => {
  it("shows a button that sends the prompt through the host", async () => {
    const sendPrompt = vi.fn();
    mount({ callTool: async () => ({ items: [] }), sendPrompt }, { empty_action: "Run an eval" });
    fireEvent.click(await screen.findByRole("button", { name: "Run an eval" }));
    expect(sendPrompt).toHaveBeenCalledWith("Run an eval");
  });

  it("shows no button without an action or without a host that can send", async () => {
    const { unmount } = mount({ callTool: async () => ({ items: [] }), sendPrompt: vi.fn() }, {});
    await screen.findByText("No experiments yet.");
    expect(screen.queryByRole("button")).toBeNull();
    unmount();
    mount({ callTool: async () => ({ items: [] }) }, { empty_action: "Run an eval" });
    await waitFor(() => expect(screen.getByText("No experiments yet.")).toBeTruthy());
    expect(screen.queryByRole("button")).toBeNull();
  });
});
