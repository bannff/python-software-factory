"use client";

import { useState } from "react";
import { Trash2 } from "lucide-react";
import { callTool } from "@/lib/api";
import { ConfirmDelete } from "@/components/ui/confirm-delete";
import { errorReason, withReason } from "@/lib/error-reason";
import { unwrapToolData } from "@/lib/tool-result-data";
import type { Crew } from "./crew-types";

/**
 * Revision-fenced crew delete behind an inline confirm. Authorization lives in
 * the server's authoring gate; a denial surfaces as the typed reason below
 * instead of the control silently disappearing.
 */
export function CrewDelete({ crew, onDeleted }: { crew: Crew; onDeleted: () => void }) {
  const [error, setError] = useState<string | null>(null);

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
