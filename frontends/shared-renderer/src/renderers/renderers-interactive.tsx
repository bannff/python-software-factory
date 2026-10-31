"use client";

import React, { useState, useCallback } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Textarea } from "../ui/textarea";
import { Select } from "../ui/select";
import { cn } from "../lib/utils";
import type { RendererProps } from "./renderer-types";
import { LazyTabContent, type TabDef } from "./renderers-lazy-tab";
import { asActionRef } from "../actions/action-ref";
import { useAction } from "../actions/use-action";

/* FormRenderer */

type FormField = {
  name: string;
  type: "text" | "number" | "select" | "textarea" | "range";
  label?: string; placeholder?: string; tooltip?: string;
  options?: { label: string; value: string }[];
  min?: number; max?: number; value?: unknown;
};

/**
 * bd:372an — this used to raw-`fetch("/api/tools/${tool}")` with `formData` as
 * the body, bypassing the BridgeAdapter seam and carrying no envelope, no
 * thread/run correlation and no transcript entry. It now dispatches through
 * `useAction`. The `action` prop carries an `ActionRef`; the server normalizes
 * legacy `props.tool` into it at ingestion, so the 18 live brick-declared
 * forms keep working with no brick edit.
 */
export function FormRenderer({ node }: RendererProps) {
  const { action, action_error, fields = [], submit_label = "Submit", className } =
    node.props as {
      action?: unknown; action_error?: string; fields?: FormField[];
      submit_label?: string; className?: string;
    };
  const ref = asActionRef(action);
  const [formData, setFormData] = useState<Record<string, unknown>>(() => {
    const init: Record<string, unknown> = {};
    for (const f of fields) init[f.name] = f.value ?? (f.type === "number" || f.type === "range" ? 0 : "");
    return init;
  });
  const { dispatch, pending, error: dispatchError, result } = useAction();
  const [confirming, setConfirming] = useState(false);
  const error = action_error ?? dispatchError;

  const handleChange = useCallback((name: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  }, []);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ref) return;
    if (ref.confirm && !confirming) { setConfirming(true); return; }
    setConfirming(false);
    await dispatch(ref, formData, formData);
  }, [ref, confirming, dispatch, formData]);

  const renderField = (field: FormField) => {
    const val = formData[field.name];
    const lbl = field.label ?? field.name;
    switch (field.type) {
      case "textarea":
        return (<div key={field.name} className="space-y-2"><label className="text-sm font-medium">{lbl}</label>
          <Textarea placeholder={field.placeholder} value={String(val ?? "")}
            onChange={(e) => handleChange(field.name, e.target.value)} /></div>);
      case "select":
        return (<div key={field.name} className="space-y-2"><label className="text-sm font-medium">{lbl}</label>
          <Select options={field.options ?? []} value={String(val ?? "")}
            onChange={(e) => handleChange(field.name, e.target.value)} /></div>);
      case "range":
        return (<div key={field.name} className="space-y-2">
          <label className="text-sm font-medium">{lbl}: {String(val)}</label>
          <input type="range" min={field.min ?? 0} max={field.max ?? 100} value={Number(val ?? 0)}
            onChange={(e) => handleChange(field.name, Number(e.target.value))} className="w-full accent-primary" /></div>);
      case "number":
        return (<div key={field.name} className="space-y-2"><label className="text-sm font-medium">{lbl}</label>
          <Input type="number" placeholder={field.placeholder} min={field.min} max={field.max}
            value={String(val ?? "")} onChange={(e) => handleChange(field.name, Number(e.target.value))} /></div>);
      default:
        return (<div key={field.name} className="space-y-2"><label className="text-sm font-medium">{lbl}</label>
          <Input type="text" placeholder={field.placeholder} value={String(val ?? "")}
            onChange={(e) => handleChange(field.name, e.target.value)} /></div>);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={cn("space-y-4", className)}>
      {fields.map(renderField)}
      <Button type="submit" variant={confirming ? "destructive" : "default"}
        disabled={pending || !ref} aria-busy={pending || undefined}>
        {pending ? "Submitting…" : confirming ? `Confirm: ${submit_label}` : submit_label}
      </Button>
      {error && (
        <div role="alert" className="rounded-md border border-destructive/50 p-3 text-sm text-destructive">
          {error}
        </div>
      )}
      {result !== null && result !== undefined && (
        <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-muted p-4 text-sm">
          {typeof result === "string" ? result : JSON.stringify(result, null, 2)}
        </pre>
      )}
    </form>
  );
}

/* TabsRenderer */

export function TabsRenderer({ node, renderChildren }: RendererProps) {
  const { tabs = [], className } = node.props as {
    tabs?: TabDef[]; className?: string;
  };
  const [active, setActive] = useState(tabs[0]?.id ?? "");
  const activeTab = tabs.find((t) => t.id === active);
  const matchedChild = node.children?.find((c) => c.id === active);

  return (
    <div className={cn("space-y-2", className)}>
      <div className="inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground">
        {tabs.map((tab) => (
          <button key={tab.id} onClick={() => setActive(tab.id)} className={cn(
            "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all",
            active === tab.id && "bg-background text-foreground shadow-sm"
          )}>{tab.label}</button>
        ))}
      </div>
      <div className="rounded-md border p-4">
        {matchedChild
          ? renderChildren(node.children!.filter((c) => c.id === active))
          : activeTab?.lazy_tool
            ? <LazyTabContent key={active} tab={activeTab} />
            : <p className="text-sm text-muted-foreground">Tab: {active}</p>}
      </div>
    </div>
  );
}

/* BreadcrumbRenderer */

export function BreadcrumbRenderer({ node }: RendererProps) {
  const { items = [], className } = node.props as {
    items?: { label: string; href?: string }[]; className?: string;
  };
  return (
    <nav aria-label="Breadcrumb" className={className}>
      <ol className="flex items-center gap-1.5 text-sm text-muted-foreground">
        {items.map((item, i) => (
          <li key={i} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-muted-foreground/50">/</span>}
            {item.href
              ? <a href={item.href} className="hover:text-foreground transition-colors">{item.label}</a>
              : <span className={i === items.length - 1 ? "text-foreground font-medium" : ""}>{item.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}
