"use client";

import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { callTool, listTools } from "@/lib/api";
import { ConfirmDelete } from "@/components/ui/confirm-delete";
import { errorReason, withReason } from "@/lib/error-reason";
import { unwrapToolData } from "@/lib/tool-result-data";
import type { Crew } from "./crew-types";

/**
 * Revision-fenced crew delete. `agent_delete_crew` is authoring-gated and the
 * gate removes it from the tool list when denied, so the control is offered
 * only when the server actually exposes the tool.
 */
export function CrewDelete({ crew, onDeleted }: { crew: Crew; onDeleted: () => void }) {
  const [available, setAvailable] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    listTools().then(({ tools }) => { if (live) setAvailable(tools.includes("agent_delete_crew")); })
      .catch(() => { if (live) setAvailable(false); });
    return () => { live = false; };
  }, []);

  if (!available) return null;

  const remove = async () => {
    setError(null);
    try {
      unwrapToolData(await callTool("agent_delete_crew", { crew_id: crew.id, expected_revision: crew.revision }));
      onDeleted();
    } catch (cause) {
      setError(withReason("Couldn’t delete this crew — it may have changed. Reopen it and retry.", errorReason(cause)));
    }
  };

  return (
    <>
      <ConfirmDelete label={`Delete crew ${crew.name}`} onConfirm={() => void remove()}
        className="inline-flex items-center gap-1.5 rounded-md border border-destructive/40 px-3.5 py-1.5 text-xs text-destructive">
        <Trash2 className="h-3.5 w-3.5" /> Delete
      </ConfirmDelete>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    </>
  );
}
