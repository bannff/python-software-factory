import { ImageResponse } from "next/og";
import { brandMark } from "./_brand-mark";

// iOS home-screen / pinned-tab icon (180x180).
// Same brand mark as app/icon.tsx, scaled up.

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(brandMark(size.width), { ...size });
}
