"use client";

/**
 * <CodeBlockMarkdownRenderer /> — replacement for the v2 default
 * `<CopilotChatAssistantMessage.MarkdownRenderer />` slot that swaps
 * Streamdown's built-in shiki code block for our project-themed
 * react-syntax-highlighter shell with a copy-to-clipboard button
 * (bd-ezy3).
 *
 * NATIVE PATTERN — leverages CopilotKit's slot system + Streamdown's
 * `components` override (Streamdown is the markdown engine v2 already
 * ships, see CopilotChatAssistantMessage.mjs L11). We pass a
 * components map that overrides only `code`; every other markdown
 * primitive (lists, tables, inline code, mermaid, math) keeps the
 * upstream rendering, so no regressions to existing markdown output.
 *
 * Wired via:
 *   <CopilotChat
 *     messageView={{
 *       assistantMessage: { markdownRenderer: CodeBlockMarkdownRenderer }
 *     }}
 *   />
 */

import type { ComponentProps } from "react";
import { Streamdown } from "streamdown";
import { CodeBlock } from "./code-block";

interface CodeBlockMarkdownRendererProps
  extends Omit<ComponentProps<typeof Streamdown>, "children"> {
  content: string;
}

// Streamdown's `components` map keys map onto JSX intrinsic elements
// (e.g. `code`, `pre`, `a`). We type the override loosely because the
// engine narrows on internal hast-util types; the runtime contract is
// "render the fenced-code body" which `<CodeBlock />` honours.
const COMPONENTS_OVERRIDE = {
  code: CodeBlock,
} as ComponentProps<typeof Streamdown>["components"];

export function CodeBlockMarkdownRenderer({
  content,
  className,
  components,
  ...rest
}: CodeBlockMarkdownRendererProps) {
  // Merge consumer-supplied components (rare, but possible via the
  // slot's partial-props variant) over our default override.
  const mergedComponents = {
    ...COMPONENTS_OVERRIDE,
    ...(components ?? {}),
  } as ComponentProps<typeof Streamdown>["components"];

  return (
    <Streamdown
      className={className}
      components={mergedComponents}
      {...rest}
    >
      {content ?? ""}
    </Streamdown>
  );
}
