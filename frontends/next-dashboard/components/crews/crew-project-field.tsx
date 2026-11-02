"use client";

import { useProjectRoots } from "@/lib/hooks/use-project-roots";
import { Field, FIELD } from "./crew-field";

/** Picker over the devtools-allowed roots; free text only when none are configured. */
export function CrewProjectField({ value, onChange, error }: {
  value: string; error?: string;
  onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
}) {
  const { roots } = useProjectRoots();
  // A saved project outside the current roots stays selectable so editing never silently drops it.
  const options = value && !roots.includes(value) ? [value, ...roots] : roots;
  return (
    <Field field="project" error={error}>
      {roots.length > 0 ? (
        <select className={FIELD} value={value} onChange={onChange}>
          <option value="">Select a project…</option>
          {options.map((root) => <option key={root} value={root}>{root}</option>)}
        </select>
      ) : (
        <input className={FIELD} value={value} onChange={onChange} placeholder="/abs/path/to/project" />
      )}
    </Field>
  );
}
