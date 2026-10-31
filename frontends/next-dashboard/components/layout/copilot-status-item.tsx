"use client";

import { useEffect, useRef } from "react";

/**
 * Captures the <cpk-web-inspector> web component and reparents it
 * into the status bar when showing the diamond button. When the
 * inspector window opens, moves it back to document.body so it
 * renders as a fixed overlay in the viewport center.
 */
export function CopilotItem() {
  const containerRef = useRef<HTMLDivElement>(null);
  const movedRef = useRef(false);

  useEffect(() => {
    /* Force localStorage state to closed */
    try {
      const key = "cpk:inspector:state";
      const raw = localStorage.getItem(key);
      if (raw) {
        const s = JSON.parse(raw);
        s.isOpen = false;
        localStorage.setItem(key, JSON.stringify(s));
      }
    } catch { /* ignore */ }

    function setup(el: HTMLElement) {
      if (movedRef.current || !containerRef.current) return;
      movedRef.current = true;

      /* Lock announcement properties */
      Object.defineProperty(el, "showAnnouncementPreview", {
        get: () => false, set: () => {}, configurable: true,
      });
      Object.defineProperty(el, "hasUnseenAnnouncement", {
        get: () => false, set: () => {}, configurable: true,
      });

      const statusBar = containerRef.current;
      const w = el as HTMLElement & { isOpen?: boolean };

      function moveToStatusBar() {
        el.style.position = "relative";
        el.style.transform = "none";
        el.style.inset = "auto";
        el.style.zIndex = "50";
        if (el.parentElement !== statusBar) statusBar.appendChild(el);
      }

      function moveToBody() {
        el.style.position = "fixed";
        el.style.transform = "";
        el.style.inset = "0";
        el.style.zIndex = "99999";
        if (el.parentElement !== document.body) {
          document.body.appendChild(el);
        }
      }

      /* Initial: put in status bar */
      moveToStatusBar();

      /* Watch for open/close via shadow DOM changes */
      const sr = el.shadowRoot;
      if (sr) {
        const obs = new MutationObserver(() => {
          if (w.isOpen) moveToBody();
          else moveToStatusBar();
        });
        obs.observe(sr, { childList: true, subtree: true });
      }
    }

    const existing = document.querySelector("cpk-web-inspector");
    if (existing) { setup(existing as HTMLElement); return; }

    const obs = new MutationObserver((_, o) => {
      const el = document.querySelector("cpk-web-inspector");
      if (el) { o.disconnect(); setup(el as HTMLElement); }
    });
    obs.observe(document.body, { childList: true, subtree: true });
    return () => obs.disconnect();
  }, []);

  return (
    <div
      ref={containerRef}
      className="flex items-center copilot-status-host"
      title="CopilotKit Inspector"
    />
  );
}
