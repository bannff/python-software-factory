"use client";

import { useState, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";

/**
 * Rotating text with particle-like character animation.
 * Uses framer-motion (already installed) — no new dependencies.
 *
 * Each character animates in/out independently with staggered
 * timing, creating a particle scatter/assemble effect.
 */

interface ParticleTextProps {
  words: string[];
  interval?: number;
  className?: string;
}

export function ParticleText({
  words,
  interval = 2500,
  className = "",
}: ParticleTextProps) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(
      () => setIndex((i) => (i + 1) % words.length),
      interval,
    );
    return () => clearInterval(timer);
  }, [words.length, interval]);

  const word = words[index];

  return (
    <div className={className} aria-live="polite">
      <AnimatePresence mode="wait">
        <motion.span
          key={word}
          className="inline-flex justify-center flex-wrap"
          initial="hidden"
          animate="visible"
          exit="exit"
          variants={{
            visible: { transition: { staggerChildren: 0.03 } },
            exit: { transition: { staggerChildren: 0.02, staggerDirection: -1 } },
          }}
        >
          {word.split("").map((char, i) => (
            <motion.span
              key={`${char}-${i}`}
              className="inline-block"
              style={{ whiteSpace: char === " " ? "pre" : undefined }}
              variants={{
                hidden: {
                  opacity: 0,
                  y: 20,
                  filter: "blur(8px)",
                  scale: 0.8,
                },
                visible: {
                  opacity: 1,
                  y: 0,
                  filter: "blur(0px)",
                  scale: 1,
                  transition: {
                    y: { type: "spring", damping: 20, stiffness: 200 },
                    scale: { type: "spring", damping: 20, stiffness: 200 },
                    filter: { duration: 0.2, ease: "easeOut" },
                  },
                },
                exit: {
                  opacity: 0,
                  y: -15,
                  filter: "blur(6px)",
                  scale: 0.9,
                  transition: { duration: 0.2 },
                },
              }}
            >
              {char}
            </motion.span>
          ))}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}
