import React from "react";
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { BridgeAdapterProvider } from "../index";
import { ItemListRenderer } from "../renderers/renderers-item-list";
import { eventCodeLabel } from "../renderers/renderers-item-list-utils";

describe("eventCodeLabel", () => {
  it("drops the brick prefix and sentence-cases a dotted event code", () => {
    expect(eventCodeLabel("game.move")).toBe("Move");
    expect(eventCodeLabel("blockchain.tx.committed")).toBe("Tx committed");
    expect(eventCodeLabel("sandbox.container_reaped")).toBe("Container reaped");
  });
  it("leaves ordinary values alone", () => {
    for (const v of ["running", "high", "training_only", "Healthy", "v1.2", "a b.c"]) expect(eventCodeLabel(v)).toBe(v);
  });
});

const rows = [
  { event_id: "1", label: "Move", game_id: "g1", event_type: "game.move" },
  { event_id: "2", label: "Created", game_id: "g2", event_type: "game.created" },
];
const props = {
  data_tool: "games_get_dashboard_summary", data_path: "$.recent_activity", item_key: "event_id",
  empty_message: "No games activity recorded yet.",
  filters: { field: "event_type", values: ["game.created", "game.move"], colors: {}, show_counts: false },
  item_layout: { title: "$.label", subtitle: "$.game_id", badge: { field: "event_type", suffix: "" } },
};

const mount = () => render(
  <BridgeAdapterProvider adapter={{ callTool: async () => ({ recent_activity: rows }) }}>
    <ItemListRenderer node={{ id: "n", component: "item_list", originalType: "item_list", props }} renderChildren={() => null} />
  </BridgeAdapterProvider>,
);

describe("ItemList event codes", () => {
  it("shows friendly filter chips and badges, never the raw code", async () => {
    mount();
    await screen.findByText("g1");
    expect(screen.queryByText("game.move")).toBeNull();
    expect(screen.queryByText("Game.move")).toBeNull();
    expect(screen.getAllByText("Move").length).toBeGreaterThanOrEqual(2);
  });

  it("filters by the raw value even though the chip shows the friendly label", async () => {
    mount();
    await screen.findByText("g1");
    fireEvent.click(screen.getByRole("button", { name: "Created" }));
    expect(screen.queryByText("g1")).toBeNull();
    expect(screen.getByText("g2")).toBeTruthy();
  });

  it("does not call every list a list of runs when a filter matches nothing", async () => {
    render(
      <BridgeAdapterProvider adapter={{ callTool: async () => ({ recent_activity: [rows[0]] }) }}>
        <ItemListRenderer node={{ id: "n", component: "item_list", originalType: "item_list", props: { ...props, filters: { ...props.filters, show_counts: false } } }} renderChildren={() => null} />
      </BridgeAdapterProvider>,
    );
    await screen.findByText("g1");
    fireEvent.click(screen.getByRole("button", { name: "Created" }));
    expect(screen.queryByText(/No runs match/)).toBeNull();
    expect(screen.getByText(/Nothing matches Created/)).toBeTruthy();
  });
});

describe("ItemList badge that repeats the title", () => {
  it("hides the badge when it says the same thing as the row title", async () => {
    render(
      <BridgeAdapterProvider adapter={{ callTool: async () => ({ recent_activity: [{ event_id: "1", label: "Bounty Posted", game_id: "b1", event_type: "blockchain.bounty.posted" }] }) }}>
        <ItemListRenderer node={{ id: "n", component: "item_list", originalType: "item_list", props: { ...props, filters: undefined } }} renderChildren={() => null} />
      </BridgeAdapterProvider>,
    );
    await screen.findByText("b1");
    expect(screen.getAllByText(/bounty posted/i)).toHaveLength(1);
  });

  it("keeps a badge that adds information", async () => {
    render(
      <BridgeAdapterProvider adapter={{ callTool: async () => ({ recent_activity: [{ event_id: "1", label: "Transaction Committed", game_id: "t1", event_type: "blockchain.tx.committed" }] }) }}>
        <ItemListRenderer node={{ id: "n", component: "item_list", originalType: "item_list", props: { ...props, filters: undefined } }} renderChildren={() => null} />
      </BridgeAdapterProvider>,
    );
    await screen.findByText("t1");
    expect(screen.getByText("Tx committed")).toBeTruthy();
  });
});
