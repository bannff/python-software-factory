/**
 * Canvas painting callbacks for the ForceGraph2D node renderer.
 * Pure rendering logic — no React dependencies.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

/** Create a nodeCanvasObject painter that highlights the selected node. */
export function makeNodePainter(selectedId: string | null) {
  return (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    // ctx.save/restore required: ForceGraph2D calls ctx.restore() after this
    // function when nodeCanvasObjectMode="replace" (the default). Without a
    // matching save() here the outer loop's save is popped, underflowing the
    // canvas state stack and throwing:
    //   TypeError: Failed to execute 'restore' on 'CanvasRenderingContext2D':
    //   The context state stack is empty.
    ctx.save();
    const label = node.name ?? node.id;
    const fontSize = Math.max(10 / globalScale, 1.5);
    const r = Math.sqrt(node.val ?? 1) * 4;
    ctx.beginPath();
    ctx.arc(node.x ?? 0, node.y ?? 0, r, 0, 2 * Math.PI);
    ctx.fillStyle = node.color ?? "#6b7280";
    ctx.fill();
    if (selectedId != null && selectedId === node.id) {
      ctx.strokeStyle = "#f59e0b";
      ctx.lineWidth = 2 / globalScale;
      ctx.stroke();
    }
    if (globalScale > 1.2) {
      ctx.font = `${fontSize}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = "rgba(255,255,255,0.85)";
      ctx.fillText(label, node.x ?? 0, (node.y ?? 0) + r + 2);
    }
    ctx.restore();
  };
}

/** Pointer-area painter — slightly larger hit area than the visible node. */
export function nodePointerAreaPaint(node: any, color: string, ctx: CanvasRenderingContext2D) {
  const r = Math.sqrt(node.val ?? 1) * 4;
  ctx.beginPath();
  ctx.arc(node.x ?? 0, node.y ?? 0, r + 2, 0, 2 * Math.PI);
  ctx.fillStyle = color;
  ctx.fill();
}
