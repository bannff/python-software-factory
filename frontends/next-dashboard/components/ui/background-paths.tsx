"use client";

import { motion } from "framer-motion";

interface PathDef {
  d: string;
  duration: number;
  delay: number;
  opacity: number;
}

const PATHS: PathDef[] = [
  { d: "M -20 80 Q 200 20 420 120",   duration: 18, delay: 0,    opacity: 0.10 },
  { d: "M 0 200 Q 150 100 400 250",   duration: 22, delay: 1.5,  opacity: 0.08 },
  { d: "M 80 -10 Q 200 150 100 350",  duration: 16, delay: 0.5,  opacity: 0.12 },
  { d: "M 300 -20 Q 450 100 350 300", duration: 20, delay: 2,    opacity: 0.09 },
  { d: "M -30 300 Q 100 200 350 400", duration: 25, delay: 0.8,  opacity: 0.07 },
  { d: "M 150 -30 Q 300 80 500 200",  duration: 17, delay: 3,    opacity: 0.11 },
  { d: "M 400 50 Q 500 200 380 400",  duration: 19, delay: 1,    opacity: 0.08 },
  { d: "M -10 150 Q 200 300 450 180", duration: 23, delay: 2.5,  opacity: 0.10 },
  { d: "M 50 350 Q 250 250 500 350",  duration: 21, delay: 0.3,  opacity: 0.09 },
  { d: "M 200 400 Q 350 300 500 450", duration: 15, delay: 1.8,  opacity: 0.07 },
  { d: "M -20 50 Q 100 180 300 80",   duration: 24, delay: 0.7,  opacity: 0.11 },
  { d: "M 100 -20 Q 250 120 200 300", duration: 18, delay: 3.5,  opacity: 0.08 },
  { d: "M 350 -10 Q 480 150 420 320", duration: 20, delay: 1.2,  opacity: 0.10 },
  { d: "M -30 400 Q 150 350 300 500", duration: 22, delay: 2.2,  opacity: 0.09 },
  { d: "M 450 100 Q 520 250 460 420", duration: 16, delay: 0.4,  opacity: 0.07 },
  { d: "M 0 280 Q 180 180 400 300",   duration: 19, delay: 2.8,  opacity: 0.12 },
  { d: "M 120 380 Q 300 420 480 360", duration: 25, delay: 1.6,  opacity: 0.08 },
  { d: "M 250 -30 Q 400 60 480 250",  duration: 17, delay: 0.9,  opacity: 0.10 },
  { d: "M -10 380 Q 80 300 200 420",  duration: 21, delay: 3.2,  opacity: 0.09 },
  { d: "M 380 380 Q 460 300 520 420", duration: 23, delay: 1.4,  opacity: 0.07 },
];

export function BackgroundPaths() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 500 500"
        preserveAspectRatio="xMidYMid slice"
        fill="none"
      >
        {PATHS.map((p, i) => (
          <motion.path
            key={i}
            d={p.d}
            stroke="url(#cx-path-grad)"
            strokeWidth={0.5}
            strokeLinecap="round"
            initial={{ pathLength: 0.4, opacity: p.opacity * 0.6 }}
            animate={{ pathLength: [0.4, 1, 0.4], opacity: [p.opacity * 0.6, p.opacity, p.opacity * 0.6] }}
            transition={{ duration: p.duration, delay: p.delay, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }}
          />
        ))}
        <defs>
          <linearGradient id="cx-path-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#8b5cf6" />
            <stop offset="100%" stopColor="#6366f1" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}
