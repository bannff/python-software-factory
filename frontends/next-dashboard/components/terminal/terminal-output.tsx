import type { ReactNode } from "react";

function line(value: string, index: number): ReactNode {
  const color = value.startsWith("+") && !value.startsWith("+++")
    ? "text-emerald-300" : value.startsWith("-") && !value.startsWith("---")
      ? "text-rose-300" : value.startsWith("@@") ? "text-violet-300" : "";
  return <span key={index} className={color}>{value}{"\n"}</span>;
}

export function TerminalOutput({ output, plain }: { output: string; plain: boolean }) {
  return <>{plain ? output : output.split("\n").map(line)}</>;
}
