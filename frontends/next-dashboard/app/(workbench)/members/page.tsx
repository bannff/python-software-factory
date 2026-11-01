"use client";
import { MembersPage } from "@/components/operations/members/members-page";

// Row 30 (feature-map) — /members. Mounts the composed Crew Members surface.
// The live members/activity data source is the deferred backend seam, so this
// renders MembersPage with an empty roster (honest "not wired" state) until
// the crew→member mapping + activity endpoint land.
export default function Page() {
  return <MembersPage members={[]} />;
}
