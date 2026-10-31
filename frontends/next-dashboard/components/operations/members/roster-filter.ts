/**
 * Row 30 (feature-map) — the Crew Members roster filter/sort model.
 *
 * The row names `pages/members/rosterFilter.ts` as "the pure filter/sort
 * model over the roster array". This is that model, in isolation: the
 * sidebar search row's persistent facets — starred-only, live state
 * (working / needs-you / unread / patrolling), origin (mine / built-in /
 * from-packages) — plus a name search and a sort (recent activity / name),
 * so package-installed crews the agent-sync writes can be collapsed.
 *
 * Pure and self-contained (no data source), so it is fully unit-testable and
 * ready for the eventual MembersPage to compose. Deferred (needs backend):
 * the crew→roster mapping itself — persisting the per-crew star, deriving
 * live state from `slots`/`autonudge` frames, and the `from-packages` origin
 * from the crew-sync — which this model consumes but does not produce.
 */

export type MemberOrigin = "mine" | "built-in" | "from-packages";
export type MemberLiveState = "working" | "needs-you" | "unread" | "patrolling" | "idle";
export type RosterSort = "recent-activity" | "name";

export interface RosterMember {
  id: string;
  name: string;
  starred: boolean;
  origin: MemberOrigin;
  state: MemberLiveState;
  /** Epoch ms of last activity; null when the member has never run. */
  lastActivityAt: number | null;
}

export interface RosterFilters {
  starredOnly?: boolean;
  /** Keep only these live states; empty/undefined = all. */
  states?: MemberLiveState[];
  /** Keep only these origins; empty/undefined = all. */
  origins?: MemberOrigin[];
  /** Case-insensitive name substring. */
  search?: string;
  /** Default: "recent-activity". */
  sort?: RosterSort;
}

function matches(member: RosterMember, filters: RosterFilters): boolean {
  if (filters.starredOnly && !member.starred) return false;
  if (filters.states && filters.states.length > 0 && !filters.states.includes(member.state)) return false;
  if (filters.origins && filters.origins.length > 0 && !filters.origins.includes(member.origin)) return false;
  const search = filters.search?.trim().toLowerCase();
  if (search && !member.name.toLowerCase().includes(search)) return false;
  return true;
}

function compare(a: RosterMember, b: RosterMember, sort: RosterSort): number {
  if (sort === "name") return a.name.localeCompare(b.name);
  // recent-activity: most-recent first, members that never ran sort last.
  const at = a.lastActivityAt ?? -Infinity;
  const bt = b.lastActivityAt ?? -Infinity;
  if (at === bt) return a.name.localeCompare(b.name);
  return bt - at;
}

/** Filter then sort a roster. Returns a new array; input is not mutated. */
export function filterAndSortRoster(
  members: readonly RosterMember[],
  filters: RosterFilters = {},
): RosterMember[] {
  const sort = filters.sort ?? "recent-activity";
  return members.filter((m) => matches(m, filters)).sort((a, b) => compare(a, b, sort));
}

export const ALL_ORIGINS: readonly MemberOrigin[] = ["mine", "built-in", "from-packages"];
export const ALL_LIVE_STATES: readonly MemberLiveState[] = [
  "working", "needs-you", "unread", "patrolling", "idle",
];
