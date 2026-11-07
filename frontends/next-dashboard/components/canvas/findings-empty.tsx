import { ListChecks, Plus } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";

export function EmptyFindings({ onAdd }: { onAdd: () => void }) {
  return <EmptyState icon={ListChecks} title="No findings yet" action={{ icon: Plus, label: "Add a finding", onClick: onAdd }} />;
}
