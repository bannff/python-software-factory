import { afterEach, describe, expect, it, vi } from "vitest";
import { startDefaultCrewSession } from "@/lib/start-default-crew-session";
import { cancelAllQuestions, getQuestionSnapshot, answerQuestion } from "@/lib/mcp-question";

afterEach(() => cancelAllQuestions());

describe("startDefaultCrewSession", () => {
  it("resolves the Crew then materializes one Session", async () => {
    const caller = vi.fn()
      .mockResolvedValueOnce({ schema_version: "v1", ok: true, data: {
        crew_id: "redteam-crew", persona_id: "reviewer",
        model_id: "ollama/llama3", project: "/work/project",
        workspace: "main", memory_scope: "redteam",
      } })
      .mockResolvedValueOnce({ schema_version: "v1", ok: true, data: { session: {
        session_id: "s-new", thread_id: "t-new", title: "New session",
        agent_id: "reviewer", model: "ollama/llama3",
        updated_at: "2026-09-13T00:00:00Z", archived_at: null, revision: 1,
        crew_id: "redteam-crew", memory_scope: "redteam",
      } } });

    const started = await startDefaultCrewSession("redteam-crew", caller);

    expect(started.session.thread_id).toBe("t-new");
    expect(caller).toHaveBeenNthCalledWith(1, "agent_resolve_crew", {
      crew_id: "redteam-crew",
    });
    expect(caller).toHaveBeenNthCalledWith(2, "session_create", expect.objectContaining({
      agent_id: "reviewer", model: "ollama/llama3", project: "/work/project",
      crew_id: "redteam-crew", memory_scope: "redteam",
    }));
  });

  it("asks the user to pick an allowed root when the stored project is refused, then retries", async () => {
    const caller = vi.fn()
      .mockResolvedValueOnce({ schema_version: "v1", ok: true, data: {
        crew_id: "redteam-crew", persona_id: "reviewer",
        model_id: "ollama/llama3", project: "/private/tmp/stale-fixture",
        workspace: "main", memory_scope: "redteam",
      } })
      .mockResolvedValueOnce({ schema_version: "v1", ok: false, error: "session_project_path_refused" })
      .mockResolvedValueOnce({ schema_version: "v1", ok: true, data: { roots: ["/work"] } })
      .mockResolvedValueOnce({ schema_version: "v1", ok: true, data: { session: {
        session_id: "s-new", thread_id: "t-new", title: "New session",
        agent_id: "reviewer", model: "ollama/llama3",
        updated_at: "2026-09-13T00:00:00Z", archived_at: null, revision: 1,
        crew_id: "redteam-crew", memory_scope: "redteam",
      } } });

    const started = startDefaultCrewSession("redteam-crew", caller);
    await vi.waitFor(() => expect(getQuestionSnapshot()).not.toBeNull());
    expect(getQuestionSnapshot()?.options).toEqual(["/work"]);
    answerQuestion("/work");

    const result = await started;
    expect(result.session.thread_id).toBe("t-new");
    expect(caller).toHaveBeenNthCalledWith(4, "session_create", expect.objectContaining({
      project: "/work",
    }));
  });

  it("fails cleanly when the user cancels the project picker", async () => {
    const caller = vi.fn()
      .mockResolvedValueOnce({ schema_version: "v1", ok: true, data: {
        crew_id: "redteam-crew", persona_id: "reviewer",
        model_id: "ollama/llama3", project: "/private/tmp/stale-fixture",
        workspace: "main", memory_scope: "redteam",
      } })
      .mockResolvedValueOnce({ schema_version: "v1", ok: false, error: "session_project_path_refused" })
      .mockResolvedValueOnce({ schema_version: "v1", ok: true, data: { roots: ["/work"] } });

    const started = startDefaultCrewSession("redteam-crew", caller);
    await vi.waitFor(() => expect(getQuestionSnapshot()).not.toBeNull());
    cancelAllQuestions();

    await expect(started).rejects.toThrow("Default crew session could not be created");
  });

  it("fails without prompting when the failure is unrelated to the project path", async () => {
    const caller = vi.fn()
      .mockResolvedValueOnce({ schema_version: "v1", ok: true, data: {
        crew_id: "redteam-crew", persona_id: "reviewer",
        model_id: "ollama/llama3", project: "/work/project",
        workspace: "main", memory_scope: "redteam",
      } })
      .mockResolvedValueOnce({ schema_version: "v1", ok: false, error: "session_binding_rejected" });

    await expect(startDefaultCrewSession("redteam-crew", caller))
      .rejects.toThrow("Default crew session could not be created");
    expect(getQuestionSnapshot()).toBeNull();
  });
});
