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
import { CREW_FIELD_HINTS, type CrewFieldKey } from "../crew-field-hints";

/**
 * Regression pin for the #140 review finding: routing every field through the
 * shared `<Field>` had put the ⓘ `<button>` inside the `<label>`, and a
 * `button` is itself labelable — so the label's labeled control became the
 * trigger and the input/select/textarea lost its implicit label association.
 * The ⓘ affordance must be a *sibling* of the label, and the label must remain
 * programmatically tied to its control.
 */
const FIELDS = Object.keys(CREW_FIELD_HINTS) as CrewFieldKey[];

const labelsOf = (element: HTMLElement) =>
  (element as unknown as { labels: NodeListOf<HTMLLabelElement> | null }).labels;

const renderEditor = () =>
  render(<CrewEditor crew={null} isDefault={false} onSaved={vi.fn()} onClose={vi.fn()} />);

describe("CrewEditor label association", () => {
  it.each(FIELDS)("%s: visible label resolves to the control and owns it", (key) => {
    renderEditor();
    const { label } = CREW_FIELD_HINTS[key];
    const control = screen.getByLabelText(label);
    expect(["INPUT", "SELECT", "TEXTAREA"]).toContain(control.tagName);

    const labels = labelsOf(control);
    expect(labels).not.toBeNull();
    expect(Array.from(labels!).map((element) => element.textContent)).toEqual([label]);
    expect(control.id).toBeTruthy();
    expect(labels![0].htmlFor).toBe(control.id);
  });

  it.each(FIELDS)("%s: the ⓘ trigger is outside the label, not the label's control", (key) => {
    renderEditor();
    const { label } = CREW_FIELD_HINTS[key];
    const trigger = screen.getByRole("button", { name: `About ${label}` });
    expect(trigger.closest("label")).toBeNull();

    const control = screen.getByLabelText(label);
    expect(labelsOf(control)![0].control).toBe(control);
    expect(labelsOf(trigger)).toHaveLength(0);
  });

  it.each(FIELDS)("%s: the label is bound to its control and clicks it, not the ⓘ", (key) => {
    renderEditor();
    const { label } = CREW_FIELD_HINTS[key];
    const control = screen.getByLabelText(label);
    const labelElement = labelsOf(control)![0];
    // Browsers activate `label.control` on a label click — jsdom does not
    // implement label activation, so the live dashboard re-checks that half.
    expect(labelElement.control).toBe(control);
    expect(labelElement.htmlFor).toBe(control.id);

    fireEvent.click(labelElement);
    expect(screen.getByRole("button", { name: `About ${label}` }).getAttribute("aria-expanded")).toBe("false");
  });

  it("clicking ⓘ toggles the hint and leaves the control alone", () => {
    renderEditor();
    const control = screen.getByLabelText("Memory scope") as HTMLInputElement;
    fireEvent.change(control, { target: { value: "scoped" } });
    const trigger = screen.getByRole("button", { name: "About Memory scope" });

    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    // jsdom does not move focus on synthetic clicks, so this pins the
    // *absence* of activation of the control by the trigger.
    expect(document.activeElement).not.toBe(control);
    expect(control.value).toBe("scoped");
    expect(control.id).toBeTruthy();
    expect(control.getAttribute("aria-describedby")).toBe("crew-memory_scope-hint");
    expect(labelsOf(control)![0].control).toBe(control);
  });
});
