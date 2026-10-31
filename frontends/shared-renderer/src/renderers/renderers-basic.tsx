"use client";

import React, { useCallback, useState } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "../ui/card";
import { Button } from "../ui/button";
import { Progress } from "../ui/progress";
import { cn } from "../lib/utils";
import type { RendererProps } from "./renderer-types";
import { asActionRef } from "../actions/action-ref";
import { useAction } from "../actions/use-action";

/* TypographyRenderer */

const TYPOGRAPHY_VARIANTS: Record<string, string> = {
  h1: "scroll-m-20 text-4xl font-extrabold tracking-tight lg:text-5xl",
  h2: "scroll-m-20 text-3xl font-semibold tracking-tight",
  h3: "scroll-m-20 text-2xl font-semibold tracking-tight",
  h4: "scroll-m-20 text-xl font-semibold tracking-tight",
  p: "leading-7",
  lead: "text-xl text-muted-foreground",
  large: "text-lg font-semibold",
  small: "text-sm font-medium leading-none",
  muted: "text-sm text-muted-foreground",
};

export function TypographyRenderer({ node }: RendererProps) {
  // bd:python-factory-3hkqx round 4 — accept all three prop aliases
  // for the Text type. Catalog docstring lists `content`; LLM agents
  // commonly emit `value`; the legacy renderer read `text`. The wire
  // is permissive at this layer (qa-tester memory `487b3ec5`).
  const props = node.props as {
    text?: string; content?: string; value?: string;
    variant?: string; className?: string;
    color?: string; size?: string | number; align?: React.CSSProperties["textAlign"];
  };
  const { variant = "p", className } = props;
  const body = props.text ?? props.content ?? props.value ?? "";
  const Tag = (variant.startsWith("h") && /^h[1-4]$/.test(variant)
    ? variant : "p") as keyof React.JSX.IntrinsicElements;
  // A2UI catalog optionalProps: color→CSS color, size→font-size
  // (number/numeric-string → px), align→text-align. Catalog-declared
  // semantic props only — free-form props.style stays at the
  // ComponentRenderer wrapper (bd:python-factory-3hkqx round 6).
  const style: React.CSSProperties = {};
  if (props.color) style.color = props.color;
  if (props.size !== undefined) {
    style.fontSize =
      typeof props.size === "number" || /^\d+$/.test(props.size)
        ? `${props.size}px`
        : props.size;
  }
  if (props.align) style.textAlign = props.align as React.CSSProperties["textAlign"];
  const hasStyle = Object.keys(style).length > 0;
  return (
    <Tag
      className={cn(TYPOGRAPHY_VARIANTS[variant] ?? TYPOGRAPHY_VARIANTS.p, className)}
      style={hasStyle ? style : undefined}
    >
      {body}
    </Tag>
  );
}

/* ButtonRenderer */

/**
 * bd:372an — this used to `fetch("/api/tools/${tool}", {method:"POST"})`:
 * no body, result discarded, errors swallowed, BridgeAdapter bypassed. It now
 * goes through `useAction`, which routes every call through the one bridge
 * seam and surfaces pending/error state. The `action` prop carries an
 * `ActionRef`; the server normalizes legacy `props.tool` into it at view
 * ingestion, so there is no back-compat branch here.
 */
export function ButtonRenderer({ node }: RendererProps) {
  const { label, variant = "default", size, disabled, action, action_error, className } =
    node.props as {
      label?: string;
      variant?: "default" | "secondary" | "destructive" | "outline" | "ghost";
      size?: "default" | "sm" | "lg" | "icon";
      disabled?: boolean; action?: unknown; action_error?: string; className?: string;
    };
  const ref = asActionRef(action);
  const { dispatch, pending, error } = useAction();
  const [confirming, setConfirming] = useState(false);

  const handleClick = useCallback(() => {
    if (!ref) return;
    if (ref.confirm && !confirming) { setConfirming(true); return; }
    setConfirming(false);
    void dispatch(ref);
  }, [ref, confirming, dispatch]);

  const verb = label ?? ref?.label ?? "Button";
  const shown = action_error ?? error;
  const button = (
    // className stays on the control itself so brick-supplied layout (e.g.
    // `w-full`) still applies. `props.style` is handled one level up by
    // ComponentRenderer's wrapper — pinned by renderers-style-passthrough.
    <Button variant={confirming ? "destructive" : variant} size={size}
      disabled={disabled || pending || !ref} onClick={handleClick}
      className={className} aria-busy={pending || undefined}>
      {pending ? "Working…" : confirming ? `Confirm: ${verb}` : verb}
    </Button>
  );
  if (!shown) return button;
  return (
    <div className="space-y-1">
      {button}
      <div role="alert" className="rounded-md border border-destructive/50 p-2 text-xs text-destructive">
        {shown}
      </div>
    </div>
  );
}

/* CardRenderer */

export function CardRenderer({ node, renderChildren }: RendererProps) {
  const { title, description, footer, className } = node.props as {
    title?: string; description?: string; footer?: string; className?: string;
  };
  return (
    <Card className={className}>
      {(title || description) && (
        <CardHeader>
          {title && <CardTitle>{title}</CardTitle>}
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
      )}
      <CardContent>{renderChildren(node.children)}</CardContent>
      {footer && (
        <CardFooter>
          <p className="text-sm text-muted-foreground">{footer}</p>
        </CardFooter>
      )}
    </Card>
  );
}

/* AlertRenderer */

const ALERT_VARIANTS: Record<string, string> = {
  default: "bg-background text-foreground",
  destructive: "border-destructive/50 text-destructive [&>svg]:text-destructive",
  warning: "border-yellow-500/50 text-yellow-700 [&>svg]:text-yellow-600",
};

export function AlertRenderer({ node }: RendererProps) {
  // bd:python-factory-3hkqx round 4 — accept catalog alias `message`
  // alongside the legacy renderer's `title`+`description`. The
  // catalog spec says required_props=["message"]; the LLM follows
  // the catalog. qa-tester memory `487b3ec5`.
  const props = node.props as {
    title?: string; description?: string; message?: string;
    variant?: string; className?: string;
  };
  const { title, description, message, variant = "default", className } = props;
  const heading = title ?? message;
  const body = description ?? (title ? message : undefined);
  return (
    <div role="alert" className={cn(
      "relative w-full rounded-lg border p-4 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4",
      ALERT_VARIANTS[variant] ?? ALERT_VARIANTS.default, className
    )}>
      {heading && <h5 className="mb-1 font-medium leading-none tracking-tight">{heading}</h5>}
      {body && <div className="text-sm [&_p]:leading-relaxed">{body}</div>}
    </div>
  );
}

/* ProgressRenderer */

export function ProgressRenderer({ node }: RendererProps) {
  const { value = 0, max = 100, label, className } = node.props as {
    value?: number; max?: number; label?: string; className?: string;
  };
  return (
    <div className={cn("space-y-1", className)}>
      {label && (
        <div className="flex justify-between text-sm">
          <span>{label}</span>
          <span className="text-muted-foreground">{Math.round((value / max) * 100)}%</span>
        </div>
      )}
      <Progress value={value} max={max} />
    </div>
  );
}

/* ListRenderer */

export function ListRenderer({ node }: RendererProps) {
  const { items = [], ordered = false, className } = node.props as {
    items?: string[]; ordered?: boolean; className?: string;
  };
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag className={cn("my-2 ml-6 list-disc [&>li]:mt-2", ordered && "list-decimal", className)}>
      {items.map((item, i) => <li key={i}>{item}</li>)}
    </Tag>
  );
}

