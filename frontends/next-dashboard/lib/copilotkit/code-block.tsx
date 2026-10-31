"use client";

/**
 * <CodeBlock /> — fenced-code renderer with syntax highlighting and a
 * copy-to-clipboard button (bd-ezy3).
 *
 * Plugged into Streamdown (the markdown engine v2 ships with) via the
 * `components.code` override, so it lives inside the v2 chat surface
 * with zero changes to the rest of the markdown pipeline. Inline
 * code (no `language-…` className) keeps the default look; only
 * fenced blocks get the highlighted shell + copy affordance.
 *
 * Theme: Prism `oneDark` — shadcn-friendly, matches the dashboard's
 * default dark theme. Light theme inherits the same palette since the
 * highlighter renders inline `<span style="color:…">`s — readable in
 * both modes.
 *
 * Languages: react-syntax-highlighter's `Prism` build registers a
 * broad set out of the box. Unknown languages fall back to plain
 * pre-formatted text inside the same shell.
 */

import { useCallback, useState } from "react";
import { Check, Copy } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

type CodeProps = {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
};

const LANGUAGE_RE = /language-([\w-]+)/;

function extractLanguage(className?: string): string | null {
  if (!className) return null;
  const m = className.match(LANGUAGE_RE);
  return m ? m[1] : null;
}

function flattenChildren(children: React.ReactNode): string {
  if (children == null) return "";
  if (typeof children === "string") return children;
  if (Array.isArray(children))
    return children.map(flattenChildren).join("");
  if (typeof children === "object" && "props" in (children as object)) {
    return flattenChildren(
      (children as { props: { children?: React.ReactNode } }).props.children,
    );
  }
  return String(children);
}

function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  const onClick = useCallback(() => {
    if (typeof window === "undefined" || !navigator?.clipboard?.writeText) {
      toast.error("Clipboard not available");
      return;
    }
    navigator.clipboard
      .writeText(code)
      .then(() => {
        setCopied(true);
        toast.success("Code copied", { duration: 1500 });
        window.setTimeout(() => setCopied(false), 1500);
      })
      .catch((err) => {
        console.error("code-block: clipboard write failed", err);
        toast.error("Couldn't copy");
      });
  }, [code]);
  return (
    <button
      type="button"
      data-testid="code-block-copy"
      onClick={onClick}
      aria-label={copied ? "Copied" : "Copy code"}
      title={copied ? "Copied!" : "Copy code"}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium transition-colors",
        "border-border/60 bg-background/60 text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {copied ? (
        <>
          <Check className="h-3 w-3 text-emerald-500" /> Copied
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" /> Copy
        </>
      )}
    </button>
  );
}

/**
 * The single export the markdown renderer plugs into Streamdown.
 *
 * `inline` is set by react-markdown / Streamdown for backtick-only
 * spans. When absent, we additionally treat code without a
 * `language-…` className AND no newlines as inline (covers Streamdown
 * builds that decide inline-ness from node position rather than the
 * `inline` prop).
 */
export function CodeBlock({ inline, className, children, ...rest }: CodeProps) {
  const code = flattenChildren(children).replace(/\n$/, "");
  const language = extractLanguage(className);
  const detectedInline = inline ?? (!language && !code.includes("\n"));

  if (detectedInline) {
    return (
      <code
        className={cn(
          "rounded bg-muted/60 px-1.5 py-0.5 font-mono text-[0.85em] text-foreground/90",
          className,
        )}
        {...rest}
      >
        {children}
      </code>
    );
  }

  return (
    <div
      data-testid="code-block"
      data-language={language ?? "text"}
      className={cn(
        "my-3 overflow-hidden rounded-lg border border-border/60 bg-card/40",
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-border/40 bg-muted/40 px-3 py-1.5">
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          {language ?? "code"}
        </span>
        <CopyButton code={code} />
      </div>
      <SyntaxHighlighter
        language={language ?? "text"}
        style={oneDark}
        wrapLongLines
        PreTag="div"
        customStyle={{
          margin: 0,
          padding: "0.75rem 0.875rem",
          background: "transparent",
          fontSize: "12.5px",
          lineHeight: "1.55",
        }}
        codeTagProps={{ className: "font-mono" }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
