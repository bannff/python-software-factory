"use client";

import React from "react";
import { cn } from "../lib/utils";
import { ICON_MAP } from "./renderers-item-list-icons";

/**
 * Single icon-resolution path for every brick-declared ``icon`` prop
 * (bd:python-factory-3jcls.1).
 *
 * Bricks declare icons as *data* in two flavours:
 *   1. a heroicons-style kebab-case NAME  — ``"icon": "cpu-chip"``
 *   2. a literal pictograph               — ``"icon": "🔭"``
 *
 * Renderers used to interpolate the raw string (``<span>{icon}</span>``),
 * which is correct for (2) and leaks an internal identifier into the UI
 * for (1) — the ML Overview showed `cpu-chip` / `beaker` / `arrow-path`
 * as right-aligned body text where a glyph belonged.
 *
 * Resolution order, applied identically everywhere:
 *   • known token  → the mapped Lucide glyph
 *   • pictograph   → rendered as text (emoji ARE the glyph)
 *   • anything else → nothing at all. An unmapped token is an internal
 *     identifier; leaking it is worse than showing no icon.
 */

const ASCII_LETTER = /[A-Za-z]/;

/** Normalize a declared icon name for map lookup (case/underscore tolerant). */
export function normalizeIconName(name: string): string {
  return name.trim().toLowerCase().replace(/_/g, "-");
}

/**
 * True when the string is its own glyph — an emoji or symbol literal.
 * Pictographs carry no ASCII letters and are a couple of code points
 * long (``⚠️``, ``🗑️``, ``🔭``, ``▶️``); identifiers and prose do.
 */
export function isPictograph(name: string): boolean {
  const s = name.trim();
  if (!s || s.length > 8) return false;
  return !ASCII_LETTER.test(s);
}

/** Resolve a declared icon name to a Lucide component, or ``null``. */
export function resolveIcon(name?: string) {
  if (!name) return null;
  return ICON_MAP[normalizeIconName(name)] ?? null;
}

export interface ViewIconProps {
  /** Icon name from a brick view payload — token or pictograph. */
  name?: string;
  /** Tailwind classes for the glyph (sizing/colour). */
  className?: string;
  /** Tailwind classes for the pictograph text span. */
  textClassName?: string;
}

/**
 * Renders a brick-declared icon, or nothing. NEVER renders a raw
 * token as text.
 */
export function ViewIcon({ name, className, textClassName }: ViewIconProps) {
  if (!name || !name.trim()) return null;
  const Icon = resolveIcon(name);
  if (Icon) {
    return <Icon aria-hidden="true" className={cn("h-4 w-4 shrink-0", className)} />;
  }
  if (isPictograph(name)) {
    return (
      <span aria-hidden="true" className={cn("shrink-0 leading-none", textClassName)}>
        {name.trim()}
      </span>
    );
  }
  return null;
}
