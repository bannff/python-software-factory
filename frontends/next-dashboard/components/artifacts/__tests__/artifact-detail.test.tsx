import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => callTool(...args) }));

import { ArtifactEditor } from "../artifact-editor";
import { ArtifactHistory } from "../artifact-history";
import { ArtifactComments } from "../artifact-comments";
import type { Artifact } from "../artifact-types";

const artifact: Artifact = {
  slug: "report", name: "Report", description: "", tags: [], kind: "text",
  content: "v1", version: 1, revision: 1, updated_at: "2026-09-11T00:00:00Z",
  folder_id: null,
};

describe("artifact detail mutations", () => {
  it("renders an explicit stale revision conflict", async () => {
    callTool.mockRejectedValueOnce(new Error("tool failed"));
    render(<ArtifactEditor artifact={artifact} onSaved={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Artifact content"), { target: { value: "v2" } });
    fireEvent.click(screen.getByRole("button", { name: /Save version/ }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/changed since it was opened/i);
  });

  it("offers additive restore only for old versions", () => {
    const onRevert = vi.fn();
    render(<ArtifactHistory versions={[
      { version: 2, kind: "text", actor_kind: "agent", event_type: "updated", created_at: "now" },
      { version: 1, kind: "text", actor_kind: "human", event_type: "created", created_at: "then" },
    ]} loading={false} reverting={null} currentVersion={2} onRevert={onRevert} />);
    expect((screen.getByLabelText("Restore version 2") as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("Restore version 1"));
    expect(onRevert).toHaveBeenCalledWith(1);
  });

  it("posts comments and advances roots to review", async () => {
    callTool.mockResolvedValue({ result: {} });
    const changed = vi.fn();
    render(<ArtifactComments slug="report" loading={false} onChanged={changed} comments={[{
      id: "a".repeat(32), root_id: "a".repeat(32), parent_id: null,
      body: "Please revise", actor_kind: "human", status: "open",
      revision: 1, created_at: "now", anchor_text: null,
    }]} />);
    fireEvent.change(screen.getByLabelText("New artifact comment"), { target: { value: "Done" } });
    fireEvent.click(screen.getByLabelText("Post comment"));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("artifacts_post_comment", { slug: "report", body: "Done" }));
    fireEvent.click(screen.getByRole("button", { name: /Mark review/ }));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("artifacts_mark_comment_review", { slug: "report", comment_id: "a".repeat(32) }));
  });

  it("shows a pending anchor from a text selection, includes it when posting, and clears it after", async () => {
    callTool.mockResolvedValue({ result: {} });
    const onClearAnchor = vi.fn();
    render(<ArtifactComments
      slug="report" loading={false} onChanged={vi.fn()} comments={[]}
      pendingAnchor="the quoted span" onClearAnchor={onClearAnchor}
    />);
    expect(screen.getByText(/Commenting on:/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("New artifact comment"), { target: { value: "fix this" } });
    fireEvent.click(screen.getByLabelText("Post comment"));
    await waitFor(() => expect(callTool).toHaveBeenCalledWith("artifacts_post_comment", {
      slug: "report", body: "fix this", anchor_text: "the quoted span",
    }));
    expect(onClearAnchor).toHaveBeenCalled();
  });

  it("renders a comment's anchor snippet, flagging it orphaned when the text no longer exists", () => {
    render(<ArtifactComments
      slug="report" loading={false} onChanged={vi.fn()} artifactContent="current body text"
      comments={[
        {
          id: "a".repeat(32), root_id: "a".repeat(32), parent_id: null,
          body: "on it", actor_kind: "human", status: "open", revision: 1,
          created_at: "now", anchor_text: "current",
        },
        {
          id: "b".repeat(32), root_id: "b".repeat(32), parent_id: null,
          body: "stale ref", actor_kind: "human", status: "open", revision: 1,
          created_at: "now", anchor_text: "no longer here",
        },
      ]}
    />);
    expect(screen.getByText(/current/).closest("div")?.className).not.toMatch(/amber/);
    expect(screen.getByText(/no longer found in the artifact/i)).toBeTruthy();
  });
});
