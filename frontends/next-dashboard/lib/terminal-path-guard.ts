/**
 * Path-traversal guard for the terminal BFF catch-all.
 *
 * Next.js decodes catch-all segments once, so a segment is rejected when it is
 * `.`/`..`, already contains a separator, carries an encoded traversal/
 * separator marker, or decodes into one. The exact terminal routes
 * (`sessions`, `sessions/<id>`, `.../attach`, `.../complete`, `shells`) contain
 * none of these, so they pass through untouched.
 */

const ENCODED_TRAVERSAL = /%2e|%2f|%5c|\\|\/|\0/i;

export function isUnsafeSegment(segment: string): boolean {
  if (segment === "." || segment === "..") return true;
  if (segment.includes("/") || segment.includes("\\")) return true;
  if (ENCODED_TRAVERSAL.test(segment)) return true;
  try {
    const decoded = decodeURIComponent(segment);
    if (decoded !== segment && (decoded === "." || decoded === ".."
        || decoded.includes("/") || decoded.includes("\\"))) return true;
  } catch { return true; } // malformed percent-encoding is rejected outright
  return false;
}

export function hasUnsafeSegment(path: readonly string[]): boolean {
  return path.some(isUnsafeSegment);
}
