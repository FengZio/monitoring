import React, { useRef, useEffect, useState, useCallback } from "react";

interface FenceCanvasProps {
  width: number;
  height: number;
  points: [number, number][];
  onPointsChange: (points: [number, number][]) => void;
  editing: boolean;
}

const SNAP_DIST = 12; // px to snap to first point for auto-close

const FenceCanvas: React.FC<FenceCanvasProps> = ({
  width, height, points, onPointsChange, editing,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [hoverNearFirst, setHoverNearFirst] = useState(false);

  const getPos = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>): [number, number] => {
      const rect = canvasRef.current!.getBoundingClientRect();
      const scaleX = width / rect.width;
      const scaleY = height / rect.height;
      return [(e.clientX - rect.left) * scaleX, (e.clientY - rect.top) * scaleY];
    }, [width, height]
  );

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, width, height);

    if (points.length === 0) return;

    const isClosed = points.length >= 3 && !editing;

    // filled polygon when closed
    if (isClosed && points.length >= 3) {
      ctx.beginPath(); ctx.moveTo(points[0][0], points[0][1]);
      for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
      ctx.closePath();
      ctx.fillStyle = "rgba(255, 50, 50, 0.08)"; ctx.fill();
    }

    // edges
    if (points.length >= 2) {
      ctx.beginPath(); ctx.moveTo(points[0][0], points[0][1]);
      for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
      // preview closing line if hovering near first point
      if (editing && points.length >= 3 && hoverNearFirst && points[0]) {
        ctx.lineTo(points[0][0], points[0][1]);
      }
      ctx.strokeStyle = "rgba(255, 50, 50, 0.9)"; ctx.lineWidth = 2;
      ctx.setLineDash(isClosed ? [] : [6, 3]);
      ctx.stroke(); ctx.setLineDash([]);
    }

    // vertices
    points.forEach(([x, y], i) => {
      const r = i === 0 ? 6 : 5;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = i === 0 ? "#FFD700" : "#FF3333"; ctx.fill();
      ctx.strokeStyle = "#fff"; ctx.lineWidth = 1; ctx.stroke();
      // label
      if (editing && points.length > 1) {
        ctx.fillStyle = "#fff"; ctx.font = "11px monospace";
        ctx.textAlign = "center"; ctx.fillText(`${i + 1}`, x, y - 12); ctx.textAlign = "start";
      }
    });
  }, [points, width, height, editing, hoverNearFirst]);

  useEffect(() => { redraw(); }, [redraw]);

  // ---- click: add point or auto-close ----
  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!editing) return;

    const pos = getPos(e);

    // auto-close if clicking near first point with >=3 points
    if (points.length >= 3) {
      const [fx, fy] = points[0];
      if (Math.hypot(pos[0] - fx, pos[1] - fy) < SNAP_DIST) {
        onPointsChange([...points]);  // close: don't add duplicate
        return;
      }
    }

    onPointsChange([...points, pos]);
  };

  // ---- move: track hover near first point ----
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (dragIdx !== null) {
      const pos = getPos(e);
      const next = [...points]; next[dragIdx] = pos;
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, width, height);
      if (next.length >= 2) {
        ctx.beginPath(); ctx.moveTo(next[0][0], next[0][1]);
        for (let i = 1; i < next.length; i++) ctx.lineTo(next[i][0], next[i][1]);
        ctx.strokeStyle = "rgba(255,50,50,0.9)"; ctx.lineWidth = 2; ctx.setLineDash([6, 3]);
        ctx.stroke(); ctx.setLineDash([]);
      }
      next.forEach(([x, y], i) => {
        ctx.beginPath(); ctx.arc(x, y, i === 0 ? 6 : 5, 0, Math.PI * 2);
        ctx.fillStyle = i === 0 ? "#FFD700" : "#FF3333"; ctx.fill();
      });
      return;
    }
    // track hover proximity to first point
    if (editing && points.length >= 3) {
      const pos = getPos(e);
      const [fx, fy] = points[0];
      const near = Math.hypot(pos[0] - fx, pos[1] - fy) < SNAP_DIST;
      if (near !== hoverNearFirst) setHoverNearFirst(near);
    }
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!editing) return;
    const pos = getPos(e);
    const idx = points.findIndex(([x, y]) => Math.hypot(x - pos[0], y - pos[1]) < 8);
    if (idx >= 0) setDragIdx(idx);
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (dragIdx === null) return;
    const pos = getPos(e);
    const next = [...points]; next[dragIdx] = pos;
    onPointsChange(next);
    setDragIdx(null);
  };

  const handleContextMenu = (e: React.MouseEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    if (!editing) return;
    const pos = getPos(e);
    const idx = points.findIndex(([x, y]) => Math.hypot(x - pos[0], y - pos[1]) < 8);
    if (idx >= 0) onPointsChange(points.filter((_, i) => i !== idx));
  };

  return (
    <canvas ref={canvasRef}
      style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
        cursor: editing ? "crosshair" : "default" }}
      onClick={handleClick} onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove} onMouseUp={handleMouseUp}
      onContextMenu={handleContextMenu} />
  );
};

export default FenceCanvas;