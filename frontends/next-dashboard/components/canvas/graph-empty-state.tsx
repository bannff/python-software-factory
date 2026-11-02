"use client";

import { Network, RefreshCw } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";

interface EmptyGraphProps {
  loading: boolean;
  hasLoaded: boolean;
  focusedRunId: string | null;
  onReload: () => void;
}

export function EmptyGraph({ loading, hasLoaded, focusedRunId, onReload }: EmptyGraphProps) {
  if (loading || !hasLoaded) return <EmptyState icon={Network} title="Loading graph…" />;
  return (
    <EmptyState icon={Network}
      title={focusedRunId ? "No attributable topology for this workflow run." : "No graph entities yet"}
      hint={focusedRunId ? `Run ${focusedRunId} has no projected nodes or relationships.` : undefined}
      action={{ icon: RefreshCw, label: "Reload", onClick: onReload }} />
  );
}
