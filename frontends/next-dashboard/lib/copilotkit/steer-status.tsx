"use client";

import { Target } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import type { SteerDeliveryState } from "./steer-delivery";

const COPY: Record<SteerDeliveryState, string> = {
  written: "Steering…",
  consumed: "Steered into the running turn",
  requeued: "Turn ended before this applied — runs as its own message",
};

export function SteerStatus({ state }: { state: SteerDeliveryState }) {
  const reduced = useReducedMotion();
  const consumed = state === "consumed";
  return (
    <motion.div
      data-steer-state={state}
      initial={consumed && !reduced ? { opacity: 0, y: 2 } : false}
      animate={{ opacity: 1, y: 0 }}
      className={consumed
        ? "relative mb-1 inline-flex items-center gap-1 pr-1 text-[11px] font-medium leading-5 text-primary"
        : "mb-1 inline-flex items-center gap-1 pr-1 text-[11px] leading-5 text-muted-foreground"}
    >
      {consumed && !reduced && (
        <motion.span aria-hidden="true" className="pointer-events-none absolute -inset-1 rounded-md border border-primary"
          initial={{ opacity: 0.55 }} animate={{ opacity: 0 }} transition={{ duration: 0.9, ease: "easeOut" }} />
      )}
      <span className={state === "written" ? "inline-flex items-center gap-1 motion-safe:animate-pulse" : "inline-flex items-center gap-1"}>
        <Target className="h-3 w-3 shrink-0" aria-hidden="true" />
        {COPY[state]}
      </span>
    </motion.div>
  );
}
