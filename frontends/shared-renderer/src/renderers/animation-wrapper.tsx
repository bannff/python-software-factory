"use client";

import React, { useEffect, useRef, useState } from "react";
import { motion, useSpring, useTransform } from "framer-motion";

type AnimationHint = {
  effect: string;
  library: string;
};

interface AnimationWrapperProps {
  animation: AnimationHint;
  children: React.ReactNode;
}

/** CSS-based animated gradient border (Magic UI border-beam equivalent). */
function BorderBeamWrapper({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative rounded-lg">
      <div
        className="pointer-events-none absolute -inset-px rounded-lg"
        style={{
          background:
            "linear-gradient(var(--border-beam-angle, 0deg), transparent 40%, hsl(var(--primary)) 50%, transparent 60%)",
          animation: "border-beam-spin 4s linear infinite",
          mask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
          maskComposite: "exclude",
          WebkitMaskComposite: "xor",
          padding: "1.5px",
        }}
      />
      {children}
      {/* styled-jsx → plain global <style> for framework-agnostic build
          (Track 6). Keyframes + @property are global by nature; names are
          unique so global scope is behaviour-equivalent. */}
      <style>{`
        @keyframes border-beam-spin {
          from { --border-beam-angle: 0deg; }
          to { --border-beam-angle: 360deg; }
        }
        @property --border-beam-angle {
          syntax: "<angle>";
          initial-value: 0deg;
          inherits: false;
        }
      `}</style>
    </div>
  );
}

/** Animated number counting up (Magic UI number-ticker equivalent). */
function NumberTickerWrapper({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [target, setTarget] = useState(0);

  useEffect(() => {
    const text = ref.current?.textContent ?? "";
    const num = parseFloat(text.replace(/[^0-9.-]/g, ""));
    if (!isNaN(num)) setTarget(num);
  }, []);

  const spring = useSpring(0, { stiffness: 50, damping: 20 });
  const display = useTransform(spring, (v) => Math.round(v).toLocaleString());

  useEffect(() => {
    spring.set(target);
  }, [target, spring]);

  return (
    <div ref={ref}>
      <span className="sr-only">{children}</span>
      <motion.span aria-hidden>{display}</motion.span>
    </div>
  );
}

/** CSS shimmer/shine on hover (Magic UI shimmer equivalent). */
function ShimmerWrapper({ children }: { children: React.ReactNode }) {
  return (
    <div className="group relative overflow-hidden">
      {children}
      <div
        className="pointer-events-none absolute inset-0 -translate-x-full group-hover:animate-shimmer"
        style={{
          background:
            "linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent)",
        }}
      />
      <style>{`
        @keyframes shimmer {
          to { transform: translateX(100%); }
        }
        .group:hover .animate-shimmer {
          animation: shimmer 0.75s ease-in-out;
        }
      `}</style>
    </div>
  );
}

/** Text fade-in word by word (Magic UI text-reveal equivalent). */
function TextRevealWrapper({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [words, setWords] = useState<string[]>([]);

  useEffect(() => {
    const text = ref.current?.textContent ?? "";
    if (text) setWords(text.split(/\s+/));
  }, []);

  if (words.length === 0) {
    return <div ref={ref}>{children}</div>;
  }

  return (
    <div ref={ref}>
      <span className="sr-only">{children}</span>
      <span aria-hidden>
        {words.map((word, i) => (
          <motion.span
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06, duration: 0.3 }}
            className="inline-block mr-1"
          >
            {word}
          </motion.span>
        ))}
      </span>
    </div>
  );
}

/** Framer-motion fade-in (opacity 0→1). */
function FadeInWrapper({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {children}
    </motion.div>
  );
}

/** Framer-motion slide-in (opacity 0→1 + translateY 20→0). */
function SlideInWrapper({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

const EFFECT_MAP: Record<string, React.FC<{ children: React.ReactNode }>> = {
  "border-beam": BorderBeamWrapper,
  "number-ticker": NumberTickerWrapper,
  shimmer: ShimmerWrapper,
  "text-reveal": TextRevealWrapper,
  "fade-in": FadeInWrapper,
  "slide-in": SlideInWrapper,
};

export function AnimationWrapper({ animation, children }: AnimationWrapperProps) {
  const Wrapper = EFFECT_MAP[animation.effect];
  if (!Wrapper) return <>{children}</>;
  return <Wrapper>{children}</Wrapper>;
}
