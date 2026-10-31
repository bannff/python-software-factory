"use client";

import { useMemo } from "react";
import { colorForType } from "@/lib/hooks/use-graph-data";

interface RadialEdge {
  direction: "→" | "←";
  otherId: string;
  otherName: string;
  relType: string;
}

interface GraphMiniRadialProps {
  centerColor: string;
  edges: RadialEdge[];
  onNodeSelect?: (id: string) => void;
}

const SIZE = 160;
const CX = SIZE / 2;
const CY = SIZE / 2;
const RADIUS = 60;

/** Simple string hash → hue for relationship type coloring */
function hashColor(s: string): string {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) & 0xffff;
  return `hsl(${h % 360}, 65%, 60%)`;
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + "…" : s;
}

export function GraphMiniRadial({ centerColor, edges, onNodeSelect }: GraphMiniRadialProps) {
  const positions = useMemo(() => {
    return edges.map((_, i) => {
      const angle = (2 * Math.PI * i) / edges.length - Math.PI / 2;
      return { x: CX + RADIUS * Math.cos(angle), y: CY + RADIUS * Math.sin(angle) };
    });
  }, [edges.length]);

  return (
    <svg
      width={SIZE}
      height={SIZE}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="mx-auto block"
      aria-label="Mini radial relationship graph"
    >
      <defs>
        <marker id="arrow-out" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L0,6 L6,3 z" fill="currentColor" className="text-muted-foreground" />
        </marker>
        <marker id="arrow-in" markerWidth="6" markerHeight="6" refX="1" refY="3" orient="auto-start-reverse">
          <path d="M0,0 L0,6 L6,3 z" fill="currentColor" className="text-muted-foreground" />
        </marker>
      </defs>

      {/* Lines */}
      {edges.map((edge, i) => {
        const { x, y } = positions[i];
        const edgeColor = hashColor(edge.relType);
        const markerId = edge.direction === "→" ? "arrow-out" : "arrow-in";
        return (
          <line
            key={i}
            x1={CX} y1={CY} x2={x} y2={y}
            stroke={edgeColor}
            strokeWidth={1}
            strokeOpacity={0.4}
            markerEnd={`url(#${markerId})`}
          />
        );
      })}

      {/* Outer nodes */}
      {edges.map((edge, i) => {
        const { x, y } = positions[i];
        const nodeColor = colorForType(edge.relType);
        const label = truncate(edge.otherName || edge.otherId, 12);
        return (
          <g
            key={i}
            onClick={() => onNodeSelect?.(edge.otherId)}
            className={onNodeSelect ? "cursor-pointer" : undefined}
            role={onNodeSelect ? "button" : undefined}
            aria-label={label}
          >
            <circle cx={x} cy={y} r={6} fill={nodeColor} fillOpacity={0.85} />
            <text
              x={x} y={y + 16}
              textAnchor="middle"
              fontSize={8}
              fill="currentColor"
              className="text-muted-foreground"
              style={{ userSelect: "none" }}
            >
              {label}
            </text>
          </g>
        );
      })}

      {/* Center node */}
      <circle cx={CX} cy={CY} r={8} fill={centerColor} fillOpacity={0.9} />
    </svg>
  );
}
