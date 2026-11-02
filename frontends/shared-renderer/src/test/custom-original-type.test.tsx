import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BridgeAdapterProvider, ComponentTree } from "../index";

const node = (component: string, originalType: string) => ({
  id: "n", component, originalType,
  props: { data_tool: "evals_list", empty_message: "Nothing here" },
});

const mount = (n: ReturnType<typeof node>) =>
  render(
    <BridgeAdapterProvider adapter={{ callTool: async () => ({ items: [] }) }}>
      <ComponentTree nodes={[n]} />
    </BridgeAdapterProvider>,
  );

describe("Custom nodes carrying a renderable originalType", () => {
  it("render with the originalType's renderer, not the unhandled-type card", async () => {
    mount(node("Custom", "item_list"));
    expect(await screen.findByText("Nothing here")).toBeTruthy();
    expect(screen.queryByText("Unhandled component type")).toBeNull();
  });

  it("still show the unhandled-type card when nothing matches", () => {
    mount(node("Custom", "mystery_widget"));
    expect(screen.getByText("Unhandled component type")).toBeTruthy();
  });
});
