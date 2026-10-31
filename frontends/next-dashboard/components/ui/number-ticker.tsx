"use client";

import { useEffect, useRef } from "react";
import { motion, useSpring, useTransform, useInView } from "framer-motion";

interface NumberTickerProps {
  value: number;
  className?: string;
  /** Duration in seconds for the spring animation */
  duration?: number;
}

/**
 * Animated number counter — rolls up/down when value changes.
 * Inspired by Magic UI's number-ticker pattern.
 */
export function NumberTicker({
  value,
  className,
  duration = 0.8,
}: NumberTickerProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: false });

  const spring = useSpring(0, {
    stiffness: 100,
    damping: 30,
    duration,
  });

  const display = useTransform(spring, (v) => Math.round(v));

  useEffect(() => {
    if (isInView) {
      spring.set(value);
    }
  }, [spring, value, isInView]);

  useEffect(() => {
    const unsubscribe = display.on("change", (latest) => {
      if (ref.current) {
        ref.current.textContent = String(latest);
      }
    });
    return unsubscribe;
  }, [display]);

  return <motion.span ref={ref} className={className} />;
}
