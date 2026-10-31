"use client";

import { useEffect, useState } from "react";
import { CopilotChatSidebar } from "./copilot-sidebar";

/**
 * Standalone chat surface for the chat popout/embed routes (rows 125, 128,
 * feature-map). Renders the existing `CopilotChatSidebar` full-viewport-width
 * with no-op chrome handlers (no close/resize in a popout). The providers it
 * needs (Workbench/Copilot) come from the app's root layout. Scaffold:
 * binding a specific `:slug` session is a deferred refinement — this ships
 * the live chat surface standalone.
 */
export function StandaloneChat() {
  const [width, setWidth] = useState(800);
  useEffect(() => {
    const update = () => setWidth(window.innerWidth);
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  return <CopilotChatSidebar onToggle={() => undefined} width={width} onResize={() => undefined} />;
}
