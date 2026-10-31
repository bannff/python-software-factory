import { ImageResponse } from "next/og";
import { brandMark } from "./_brand-mark";

// Browser-tab favicon for Companion X.
// Next.js generates a 32x32 PNG at build time from this component.
// The visual mark lives in ./_brand-mark.tsx — change it there.

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(brandMark(size.width), { ...size });
}
