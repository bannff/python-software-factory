"use client";

/**
 * One input per schema property (bd:3jcls.4). Presentation only — the
 * derivation lives in `lib/schema-form.ts` so it is testable against real
 * shipped schemas.
 *
 * Required fields carry `required` + `aria-required`; enums render as a
 * `Select`; numbers/integers as `type="number"`; object/array params as a JSON
 * textarea (honest about what they are rather than pretending otherwise).
 */

import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { FormField } from "@/lib/schema-form";

interface ToolArgFieldsProps {
  fields: FormField[];
  values: Record<string, string>;
  onChange: (name: string, value: string) => void;
  /** Focused first so the form is usable without touching the mouse. */
  firstFieldRef?: React.Ref<HTMLInputElement>;
}

const CONTROL =
  "h-7 rounded-sm border-border/60 bg-card/40 px-2 py-0 text-[11px] font-mono";

export function ToolArgFields({
  fields, values, onChange, firstFieldRef,
}: ToolArgFieldsProps) {
  if (fields.length === 0) {
    return (
      <p className="text-[11px] text-muted-foreground">
        No arguments — submit to run.
      </p>
    );
  }
  return (
    <div className="grid gap-1.5">
      {fields.map((field, index) => {
        const id = `arg-${field.name}`;
        const shared = {
          id,
          name: field.name,
          value: values[field.name] ?? "",
          required: field.required,
          "aria-required": field.required,
          "aria-describedby": field.description ? `${id}-hint` : undefined,
        };
        return (
          <div key={field.name} className="grid grid-cols-[9rem_1fr] items-center gap-2">
            <label
              htmlFor={id}
              className="truncate text-right font-mono text-[11px] text-muted-foreground"
              title={field.description || field.name}
            >
              {field.name}
              {field.required && <span className="text-amber-500/90"> *</span>}
            </label>
            {field.kind === "enum" ? (
              <Select
                {...shared}
                className={CONTROL}
                options={field.options.map((o) => ({ label: o, value: o }))}
                onChange={(e) => onChange(field.name, e.target.value)}
              />
            ) : field.kind === "boolean" ? (
              <Select
                {...shared}
                className={CONTROL}
                options={[
                  { label: "false", value: "false" },
                  { label: "true", value: "true" },
                ]}
                onChange={(e) => onChange(field.name, e.target.value)}
              />
            ) : field.kind === "json" ? (
              <Textarea
                {...shared}
                rows={2}
                placeholder="JSON"
                className="min-h-0 rounded-sm border-border/60 bg-card/40 px-2 py-1 font-mono text-[11px]"
                onChange={(e) => onChange(field.name, e.target.value)}
              />
            ) : (
              <Input
                {...shared}
                ref={index === 0 ? firstFieldRef : undefined}
                type={field.kind === "string" ? "text" : "number"}
                step={field.kind === "integer" ? 1 : "any"}
                placeholder={field.nullable ? "optional" : field.kind}
                className={CONTROL}
                onChange={(e) => onChange(field.name, e.target.value)}
              />
            )}
            {field.description && (
              <span id={`${id}-hint`} className="sr-only">
                {field.description}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
