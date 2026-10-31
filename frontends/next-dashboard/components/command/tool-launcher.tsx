"use client";

/**
 * Stage 2 of the palette: the generated argument form (bd:3jcls.4).
 *
 * Submit goes through `useAction().dispatch`, the SAME hook `ButtonRenderer`
 * and `FormRenderer` use, so this surface inherits the server-side chokepoint
 * (`ui_dispatch_action`), the human-provenance hint, view invalidation and the
 * transcript mirror for free. There is deliberately no second dispatch path
 * and no `fetch` in this file — a grep canary fails the build if one appears.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAction, type ActionRef } from "@companion-x/shared-renderer";
import { Button } from "@/components/ui/button";
import {
  coerceValues, deriveFields, initialValues, missingRequired,
} from "@/lib/schema-form";
import type { CatalogTool } from "@/lib/tool-catalog";
import { ResolvedCall } from "./resolved-call";
import { ToolArgFields } from "./tool-arg-fields";

interface ToolLauncherProps {
  tool: CatalogTool;
  onBack: () => void;
}

export function ToolLauncher({ tool, onBack }: ToolLauncherProps) {
  const fields = useMemo(() => deriveFields(tool.input_schema), [tool]);
  const [values, setValues] = useState<Record<string, string>>(
    () => initialValues(fields),
  );
  const { dispatch, pending, error, result, succeeded } = useAction();
  const firstField = useRef<HTMLInputElement>(null);

  useEffect(() => setValues(initialValues(fields)), [fields]);
  useEffect(() => firstField.current?.focus(), [tool.qualified_name]);

  const args = useMemo(() => coerceValues(fields, values), [fields, values]);
  const missing = useMemo(() => missingRequired(fields, values), [fields, values]);

  /**
   * `qualified_name`, not `name`. Both resolve — `candidate_names()` in
   * `a2ui/action_resolve.py` tries the prefixed and unprefixed form, and
   * `qualified_name()` is prefix-idempotent (`action_resolve.py:38`). But the
   * qualified form is what the aggregator actually invokes, so it is also the
   * only form that still resolves when the `brick_tools` probe is absent
   * (`build_tool_resolver` returns `None`) and the server falls back to
   * `qualified_name(brick, ref.tool)` verbatim. Using it here also keeps the
   * resolved-call preview honest: the string shown is the string dispatched.
   */
  const action: ActionRef = useMemo(
    () => ({ brick: tool.brick, tool: tool.qualified_name, label: tool.qualified_name }),
    [tool],
  );

  const onChange = useCallback((name: string, value: string) => {
    setValues((prev) => ({ ...prev, [name]: value }));
  }, []);

  const submit = useCallback(
    (event: React.FormEvent) => {
      event.preventDefault();
      if (missing.length > 0 || pending) return;
      void dispatch(action, args);
    },
    [action, args, dispatch, missing.length, pending],
  );

  return (
    <form onSubmit={submit} className="space-y-3 p-3" aria-label={`Run ${tool.qualified_name}`}>
      <div className="flex items-baseline gap-2">
        <button
          type="button"
          onClick={onBack}
          className="rounded-sm px-1 text-[11px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          ← back
        </button>
        <span className="font-mono text-xs text-foreground">{tool.qualified_name}</span>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {tool.category}
        </span>
      </div>
      {tool.description && (
        <p className="text-[11px] leading-snug text-muted-foreground">{tool.description}</p>
      )}

      <ToolArgFields
        fields={fields}
        values={values}
        onChange={onChange}
        firstFieldRef={firstField}
      />

      <ResolvedCall
        brick={action.brick}
        tool={action.tool}
        args={args}
        missing={missing}
      />

      <div className="flex items-center gap-2">
        <Button
          type="submit"
          size="sm"
          disabled={pending || missing.length > 0}
          className="h-7 rounded-sm px-3 text-[11px]"
        >
          {pending ? "Running…" : "Run"}
        </Button>
        <span className="text-[10px] text-muted-foreground">Esc to close</span>
      </div>

      {error && (
        <pre
          role="alert"
          data-testid="action-error"
          className="max-h-32 overflow-auto rounded-sm border border-destructive/40 bg-destructive/10 p-2 font-mono text-[11px] text-destructive"
        >
          {error}
        </pre>
      )}
      {succeeded && (
        <pre
          data-testid="action-result"
          className="max-h-40 overflow-auto rounded-sm border border-border/60 bg-card/40 p-2 font-mono text-[11px] text-foreground"
        >
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </form>
  );
}
