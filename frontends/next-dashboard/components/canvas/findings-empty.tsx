import { ListChecks, Plus, RefreshCw, TriangleAlert } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";

export function EmptyFindings({ onAdd }: { onAdd: () => void }) {
  return <EmptyState icon={ListChecks} title="No findings yet" action={{ icon: Plus, label: "Add a finding", onClick: onAdd }} />;
}

/** The read failed: say so rather than claim there are none. */
export function FindingsUnavailable({ onRetry }: { onRetry: () => void }) {
  return <EmptyState icon={TriangleAlert} title="Findings are unavailable right now"
    hint="They couldn't be read from the graph store. Try again in a moment."
    action={{ icon: RefreshCw, label: "Try again", onClick: onRetry }} />;
}
