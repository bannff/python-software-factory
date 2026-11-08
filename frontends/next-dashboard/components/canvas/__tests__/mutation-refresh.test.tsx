import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useEffect } from "react";
import { Refreshable } from "../refreshable";
import { useMutationRefresh } from "../refresh-context";

function Mutator() {
  const { notify } = useMutationRefresh();
  return <button type="button" onClick={notify}>mutate</button>;
}

function Reader({ onRead }: { onRead: (version: number) => void }) {
  const { version } = useMutationRefresh();
  useEffect(() => { onRead(version); }, [version, onRead]);
  return null;
}

describe("mutation refresh", () => {
  it("re-reads siblings after a mutation without remounting the mutator", () => {
    const onRead = vi.fn();
    const onMutatorMount = vi.fn();
    function Tracked() { useEffect(() => { onMutatorMount(); }, []); return <Mutator />; }
    render(<Refreshable label="chain"><Tracked /><Reader onRead={onRead} /></Refreshable>);
    expect(onRead).toHaveBeenLastCalledWith(0);
    act(() => { fireEvent.click(screen.getByText("mutate")); });
    expect(onRead).toHaveBeenLastCalledWith(1);
    expect(onMutatorMount).toHaveBeenCalledTimes(1);
  });

  it("is a harmless no-op outside a Refreshable", () => {
    render(<Mutator />);
    expect(() => fireEvent.click(screen.getByText("mutate"))).not.toThrow();
  });
});
