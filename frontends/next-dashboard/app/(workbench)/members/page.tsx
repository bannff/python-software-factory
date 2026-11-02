import { redirect } from "next/navigation";

// A crew is one persona + project, so a "member" is a crew; the Crews tab is
// the roster. No live per-member state source exists to justify a second page.
export default function Page() {
  redirect("/crews");
}
