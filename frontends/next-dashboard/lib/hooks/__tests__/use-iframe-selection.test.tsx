import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { useIframeSelection } from "../use-iframe-selection";
import { ARTIFACT_SELECTION_MESSAGE } from "@/lib/artifacts/iframe-selection";

function Harness({ onSelect }: { onSelect: (t: string) => void }) {
  useIframeSelection(onSelect);
  return null;
}

const post = (data: unknown) =>
  window.dispatchEvent(new MessageEvent("message", { data }));

describe("useIframeSelection (row 65, feature-map)", () => {
  it("calls onSelect with the validated selection text", () => {
    const onSelect = vi.fn();
    render(<Harness onSelect={onSelect} />);
    post({ type: ARTIFACT_SELECTION_MESSAGE, text: "  quoted  span " });
    expect(onSelect).toHaveBeenCalledWith("quoted span");
  });

  it("ignores unrelated / malformed messages", () => {
    const onSelect = vi.fn();
    render(<Harness onSelect={onSelect} />);
    post({ type: "something-else", text: "x" });
    post("not-an-object");
    post({ type: ARTIFACT_SELECTION_MESSAGE, text: "   " });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("detaches the listener on unmount", () => {
    const onSelect = vi.fn();
    const { unmount } = render(<Harness onSelect={onSelect} />);
    unmount();
    post({ type: ARTIFACT_SELECTION_MESSAGE, text: "after unmount" });
    expect(onSelect).not.toHaveBeenCalled();
  });
});
