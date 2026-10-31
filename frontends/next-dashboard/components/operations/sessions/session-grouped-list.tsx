import type { SessionSummary } from "@/lib/hooks/use-session-list";
import { SessionCard } from "./session-card";
import type { SessionGroup } from "./session-groups";

export function SessionGroupedList({ groups, agentNames, activeThreadId, selectedId, onSelect }: {
  groups: SessionGroup[];
  agentNames: Map<string, string>;
  activeThreadId?: string;
  selectedId: string | null;
  onSelect: (session: SessionSummary) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      {groups.map((group) => (
        <section key={group.id} aria-labelledby={`sessions-group-${group.id}`}>
          <h2 id={`sessions-group-${group.id}`}
            className="mb-2 text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
            {group.label}
          </h2>
          <div className="flex flex-col gap-2" role="list">
            {group.sessions.map((session) => (
              <div role="listitem" key={session.session_id}>
                <SessionCard session={session} agentName={agentNames.get(session.agent_id)}
                  active={session.thread_id === activeThreadId}
                  selected={session.session_id === selectedId}
                  onSelect={() => onSelect(session)} />
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
