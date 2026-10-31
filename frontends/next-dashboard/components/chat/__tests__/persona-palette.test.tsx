/**
 * Persona '/' palette wiring test (bd:python-factory-d4roe.3, Phase 2).
 *
 * Renders a real `<CopilotKitProvider>` from `@copilotkitnext/react`
 * so the palette's `useCopilotKit().copilotkit.setProperties(...)` call
 * exercises the actual installed `@copilotkitnext/core`. We mock the
 * `/api/personas` fetch (via the `listPersonas` API client) and assert:
 *
 *   1. personas render in the popover after it opens, and
 *   2. picking one calls `setProperties` MERGING the existing
 *      properties with `companion_x_agent_id` — so the next run carries
 *      it in `RunAgentInput.forwardedProps` without clobbering other
 *      forwarded props.
 *
 * This pins the FE half of the selection channel ratified by
 * strands-expert 6e22d1bb + meta-architect a19ef414.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import * as React from "react";
import { CopilotKitProvider, useCopilotKit } from "@copilotkit/react-core/v2";

const listPersonasMock = vi.fn();
vi.mock("@/lib/api", () => ({
  listPersonas: () => listPersonasMock(),
}));

import { PersonaPalette } from "../persona-palette";

const PERSONAS = [
  { id: "companion-x-default", name: "Companion X", description: "default sec workbench", model: "claude" },
  { id: "grape-grower", name: "Grape Grower", description: "wine domain", model: "claude" },
];

function renderPalette() {
  return render(
    <CopilotKitProvider>
      <PersonaPalette />
    </CopilotKitProvider>,
  );
}

describe("PersonaPalette", () => {
  beforeEach(() => {
    listPersonasMock.mockReset();
    listPersonasMock.mockResolvedValue({ personas: PERSONAS, count: PERSONAS.length });
  });

  it("loads personas and lists them when opened", async () => {
    await act(async () => {
      renderPalette();
    });
    // Open the popover (trigger button wraps the persona label).
    await act(async () => {
      fireEvent.click(screen.getByTitle(/switch chat persona/i));
    });
    await waitFor(() => {
      expect(screen.getByText("Grape Grower")).toBeTruthy();
      expect(screen.getByText("Companion X")).toBeTruthy();
    });
  });

  it("picking a persona merges companion_x_agent_id into forwardedProps", async () => {
    // Capture the live core via a sibling consumer.
    let core: { setProperties: (p: Record<string, unknown>) => void; properties: Record<string, unknown> } | undefined;
    function Capture() {
      core = useCopilotKit().copilotkit as typeof core;
      return null;
    }

    await act(async () => {
      render(
        <CopilotKitProvider>
          <Capture />
          <PersonaPalette />
        </CopilotKitProvider>,
      );
    });

    // Seed an existing forwarded prop so we can assert the merge.
    await act(async () => {
      core!.setProperties({ existing_prop: "keep-me" });
    });

    await act(async () => {
      fireEvent.click(screen.getByTitle(/switch chat persona/i));
    });
    await waitFor(() => expect(screen.getByText("Grape Grower")).toBeTruthy());

    await act(async () => {
      fireEvent.click(screen.getByText("Grape Grower"));
    });

    expect(core!.properties.companion_x_agent_id).toBe("grape-grower");
    // Existing forwarded prop preserved (setProperties replaces wholesale,
    // so the palette MUST merge — this asserts it does).
    expect(core!.properties.existing_prop).toBe("keep-me");
  });
});
