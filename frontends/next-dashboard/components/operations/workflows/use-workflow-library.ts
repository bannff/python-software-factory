"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { callTool, listTools } from "@/lib/api";
import {
  parseDefinitions, parseOk, parseRuns, parseStartRun,
  type WorkflowDefinitionSummary, type WorkflowRun,
} from "./workflow-library-types";

/**
 * Workflow library (feature-map row 42): saved dynamic-workflow definitions
 * and their runs. Backed entirely by tools that already existed —
 * ``workflow.get_workflow_registry`` (real definitions loaded from on-disk
 * YAML at process start) / ``workflow.start_run`` / ``workflow.list_runs`` /
 * ``workflow.cancel_run`` / ``workflow.authoring.upsert_workflow_definition``
 * / ``workflow.authoring.delete_workflow_definition`` — this view was the
 * only missing piece, same shape as Memory/Knowledge's own history.
 *
 * Authoring (create/delete a definition) is gated the same way Steering's
 * create/delete is: hidden entirely when the authoring tool is not in the
 * live catalog, never a disabled-looking control that silently does nothing.
 */
export function useWorkflowLibrary() {
  const [definitions, setDefinitions] = useState<WorkflowDefinitionSummary[]>([]);
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [canAuthor, setCanAuthor] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [defs, runsRaw, tools] = await Promise.all([
        callTool("workflow.get_workflow_registry", {}),
        callTool("workflow.list_runs", {}),
        listTools(),
      ]);
      if (!mounted.current) return;
      setDefinitions(parseDefinitions(defs));
      setRuns(parseRuns(runsRaw));
      setCanAuthor(tools.tools.includes("workflow.authoring.upsert_workflow_definition"));
      setError(null);
    } catch {
      if (mounted.current) setError("Workflow library unavailable");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => { mounted.current = false; };
  }, [refresh]);

  const createDefinition = useCallback(async (id: string, yamlText: string): Promise<string | null> => {
    try {
      const result = await callTool("workflow.authoring.upsert_workflow_definition", {
        id, yaml_or_object: yamlText,
      });
      if (!parseOk(result)) return "That definition was rejected.";
      await refresh();
      return null;
    } catch (cause) {
      return cause instanceof Error ? cause.message : "Couldn't save that definition.";
    }
  }, [refresh]);

  const deleteDefinition = useCallback(async (id: string): Promise<boolean> => {
    try {
      const result = await callTool("workflow.authoring.delete_workflow_definition", { id });
      const ok = parseOk(result);
      if (ok) await refresh();
      return ok;
    } catch {
      return false;
    }
  }, [refresh]);

  const startRun = useCallback(async (workflowNameOrId: string): Promise<string | null> => {
    try {
      const result = parseStartRun(await callTool("workflow.start_run", {
        workflow_name_or_id: workflowNameOrId, input: {},
      }));
      if (result) await refresh();
      return result?.runId ?? null;
    } catch {
      return null;
    }
  }, [refresh]);

  const cancelRun = useCallback(async (runId: string): Promise<boolean> => {
    try {
      await callTool("workflow.cancel_run", { run_id: runId });
      await refresh();
      return true;
    } catch {
      return false;
    }
  }, [refresh]);

  return {
    definitions, runs, canAuthor, loading, error,
    refresh, createDefinition, deleteDefinition, startRun, cancelRun,
  };
}
