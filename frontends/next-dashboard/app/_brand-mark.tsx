/**
 * Shared brand-mark renderer used by app/icon.tsx and app/apple-icon.tsx.
 *
 * Lucide `Sparkles` glyph rendered on a transparent background. We inline
 * the SVG path data (rather than importing from lucide-react) because both
 * favicon routes run on the Edge via Next's `ImageResponse` / Satori
 * pipeline, which prefers serialisable JSX with no extra runtime work.
 *
 * The colour matches the sidebar's active tint (violet-400, #a78bfa) so
 * the favicon, ActivityBar, and the topbar mark all sing the same note.
 */

const STROKE = "#a78bfa"; // violet-400 — matches the sidebar's active tint

function Sigil(pixelSize: number) {
  // Stroke width is hand-tuned for legibility at 16px (Chrome's tab favicon
  // size). Lucide's source uses 2 on a 24-unit viewBox; we bump to 2.4 so
  // the glyph stays bold when the OS scales it down.
  return (
    <svg
      width="100%"
      height="100%"
      viewBox="0 0 24 24"
      fill="none"
      stroke={STROKE}
      strokeWidth={pixelSize >= 64 ? 1.8 : 2.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
      <path d="M20 3v4" />
      <path d="M22 5h-4" />
      <path d="M4 17v2" />
      <path d="M5 18H3" />
    </svg>
  );
}

export function brandMark(pixelSize: number) {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        // Transparent background — the glyph carries the brand on its own.
        background: "transparent",
      }}
    >
      {Sigil(pixelSize)}
    </div>
  );
}
