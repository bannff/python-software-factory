"use client";

import {
  BarChart3, Shield, ShieldAlert, Beaker, Database, Clock, Brain,
  Wrench, FlaskConical, ShieldCheck, Bug, AlertTriangle, Activity,
  Cpu, Box, Boxes, SlidersHorizontal, RefreshCw, CircleCheck, Network,
  Server, FileText, Users, Trophy, Layers, Puzzle, Play, ClipboardList,
  Zap, Bell, Banknote, List, Circle, Upload, Info, Link2, Coins,
  type LucideIcon,
} from "lucide-react";

/**
 * Maps icon name tokens (from brick view declarations) to Lucide icons.
 *
 * Consumed exclusively through ``ViewIcon`` (``renderers-icon.tsx``),
 * which looks keys up case- and underscore-insensitively and renders
 * NOTHING for an unmapped token rather than leaking the identifier
 * (bd:python-factory-3jcls.1). Keys are the heroicons-style kebab-case
 * names bricks emit; add a mapping here when a brick declares a new one.
 */
export const ICON_MAP: Record<string, LucideIcon> = {
  // Charts / metrics
  chart: BarChart3,
  "chart-bar": BarChart3,
  "chart-bar-square": BarChart3,
  metrics: BarChart3,
  activity: Activity,
  pulse: Activity,
  // Security
  shield: Shield,
  "shield-alert": ShieldAlert,
  "shield-check": ShieldCheck,
  "shield-exclamation": ShieldAlert,
  bug: Bug,
  security: ShieldAlert,
  // Science / experiments
  beaker: Beaker,
  flask: FlaskConical,
  evals: Beaker,
  // Compute / ML
  "cpu-chip": Cpu,
  brain: Brain,
  machine_learning: Brain,
  "adjustments-horizontal": SlidersHorizontal,
  "arrow-path": RefreshCw,
  // Objects / storage
  cube: Box,
  "cube-transparent": Boxes,
  database: Database,
  "circle-stack": Database,
  "rectangle-stack": Layers,
  "server-stack": Server,
  network: Network,
  // Documents
  document: FileText,
  "document-text": FileText,
  "clipboard-document-list": ClipboardList,
  list: List,
  // Status
  "alert-triangle": AlertTriangle,
  "exclamation-triangle": AlertTriangle,
  "check-circle": CircleCheck,
  "information-circle": Info,
  bell: Bell,
  clock: Clock,
  // Misc
  wrench: Wrench,
  bolt: Zap,
  users: Users,
  trophy: Trophy,
  "puzzle-piece": Puzzle,
  play: Play,
  banknotes: Banknote,
  "arrow-up-tray": Upload,
  link: Link2,
  coins: Coins,
  default: Circle,
};
