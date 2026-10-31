import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

vi.mock("@/lib/hooks/use-personas", () => ({
  usePersonas: () => ({ personas: [{ id: "redteam", name: "Red Team" }], loading: false, error: null, refresh: vi.fn() }),
}));
vi.mock("@/lib/hooks/use-model-catalog", () => ({
  useModelCatalog: () => ({ models: [], groups: [], loading: false, error: null, refresh: vi.fn() }),
}));
vi.mock("@/lib/api", () => ({ callTool: vi.fn() }));

import { CrewEditor } from "../crew-editor";
import { CREW_FIELD_HINTS, CREW_FORM_HINT, type CrewFieldKey } from "../crew-field-hints";

// Visible label -> how the control is looked up (the shared <Field> label).
const CASES: { key: CrewFieldKey; control: string }[] = [
  { key: "id", control: "Crew ID" },
  { key: "name", control: "Name" },
  { key: "persona_id", control: "Persona" },
  { key: "model", control: "Model" },
  { key: "project", control: "Project path" },
  { key: "memory_scope", control: "Memory scope" },
  { key: "description", control: "Description" },
  { key: "triggers", control: "Triggers (comma-separated)" },
];

const renderEditor = () =>
  render(<CrewEditor crew={null} isDefault={false} onSaved={vi.fn()} onClose={vi.fn()} />);

describe("CrewEditor per-field hints", () => {
  it("covers every field the form renders", () => {
    expect(CASES.map((c) => c.key).sort()).toEqual(Object.keys(CREW_FIELD_HINTS).sort());
  });

  it.each(CASES)("wires the $key hint: label -> describedby -> text", ({ key, control }) => {
    renderEditor();
    const field = CREW_FIELD_HINTS[key];
    // The affordance is a real, keyboard-reachable button next to the label.
    const trigger = screen.getByRole("button", { name: `About ${field.label}` }) as HTMLButtonElement;
    expect(trigger.tagName).toBe("BUTTON");
    expect(trigger.getAttribute("type")).toBe("button");

    // The control points at the hint element via aria-describedby.
    const input = screen.getByLabelText(control);
    expect(input.getAttribute("aria-describedby")).toBe(`crew-${key}-hint`);

    const hint = document.getElementById(`crew-${key}-hint`);
    expect(hint).not.toBeNull();
    expect(hint!.textContent).toBe(field.hint);
    expect(hint!.getAttribute("role")).toBe("note");
  });

  it.each(CASES)("reveals the $key hint to the keyboard without a pointer", ({ key, control }) => {
    renderEditor();
    const trigger = screen.getByRole("button", { name: `About ${CREW_FIELD_HINTS[key].label}` });
    const hint = document.getElementById(`crew-${key}-hint`)!;
    // Hidden until revealed, but already referenced by the control for AT.
    expect(hint.hasAttribute("hidden")).toBe(true);
    expect(screen.getByLabelText(control).getAttribute("aria-describedby")).toBe(`crew-${key}-hint`);

    trigger.focus();
    expect(document.activeElement).toBe(trigger);
    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(hint.hasAttribute("hidden")).toBe(false);

    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(hint.hasAttribute("hidden")).toBe(true);
  });

  it("states the sourced semantics the issue calls out", () => {
    renderEditor();
    expect(CREW_FIELD_HINTS.model.hint).toContain("inherit");
    expect(CREW_FIELD_HINTS.model.hint).toContain("persona");
    expect(CREW_FIELD_HINTS.project.hint).toContain("tool_execution_failed");
    expect(CREW_FIELD_HINTS.memory_scope.hint).toContain("^[a-z0-9][a-z0-9_-]{0,63}$");
    expect(CREW_FIELD_HINTS.id.hint).toContain("Immutable");
    expect(CREW_FIELD_HINTS.triggers.hint).toContain("no agent runtime consumes them");
  });

  it("exposes a form-level crew explanation", () => {
    renderEditor();
    const trigger = screen.getByRole("button", { name: "About crew" });
    trigger.focus();
    expect(document.activeElement).toBe(trigger);
    fireEvent.click(trigger);
    const hint = document.getElementById("crew-form-hint")!;
    expect(hint.hasAttribute("hidden")).toBe(false);
    expect(hint.textContent).toBe(CREW_FORM_HINT);
    expect(screen.getByText(/not a runtime/)).toBeTruthy();
  });
});
