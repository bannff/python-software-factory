"use client";

import { useEffect, useState } from "react";
import { CopilotChatSidebar } from "./copilot-sidebar";

/**
 * Standalone chat surface for the chat popout/embed routes (rows 125, 128,
 * feature-map). Renders the existing `CopilotChatSidebar` full-viewport-width
 * without close/resize controls (a popout has nothing to collapse into). The providers it
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
  return <CopilotChatSidebar width={width} />;
}
