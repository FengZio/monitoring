import React, { useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from "react";
import type { Detection, TrackState } from "../types";

const COLORS: Record<string, string> = {
  person: "#00FF00", car: "#FF8800", truck: "#FF4444",
  motorcycle: "#44AAFF", bicycle: "#FFAA00", bus: "#CC44FF",
};
const DEFAULT_COLOR = "#FF00FF";
const FENCE_COLOR = "rgba(255, 50, 50, 0.85)";
const FENCE_FILL = "rgba(255, 50, 50, 0.08)";

export interface VideoPanelHandle { getImageElement: () => HTMLImageElement | null; }

interface Props {
  streaming: boolean;
  previewImage: string | null;
  imageSrc: string | null;
  width: number;
  height: number;
  detections: Detection[];
  tracks: TrackState[];
  fencePoints: [number, number][];
}

const VideoPanel = forwardRef<VideoPanelHandle, Props>(
  ({ streaming, previewImage, imageSrc, width, height, detections, tracks, fencePoints }, ref) => {
    const imgRef = useRef<HTMLImageElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    useImperativeHandle(ref, () => ({ getImageElement: () => imgRef.current }));

    const draw = useCallback(() => {
      const canvas = canvasRef.current;
      const img = imgRef.current;
      if (!canvas || !img) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const vw = img.naturalWidth || width || 640;
      const vh = img.naturalHeight || height || 480;
      if (vw === 0 || vh === 0) return;
      if (canvas.width !== vw || canvas.height !== vh) { canvas.width = vw; canvas.height = vh; }
      ctx.clearRect(0, 0, vw, vh);

      // Fence
      if (fencePoints.length >= 3) {
        ctx.beginPath(); ctx.moveTo(fencePoints[0][0], fencePoints[0][1]);
        for (let i = 1; i < fencePoints.length; i++) ctx.lineTo(fencePoints[i][0], fencePoints[i][1]);
        ctx.closePath();
        ctx.fillStyle = FENCE_FILL; ctx.fill();
        ctx.strokeStyle = FENCE_COLOR; ctx.lineWidth = 2; ctx.setLineDash([6, 3]); ctx.stroke(); ctx.setLineDash([]);
        fencePoints.forEach(([x, y]) => { ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fillStyle = FENCE_COLOR; ctx.fill(); });
      }

      // Detections
      detections.forEach((det) => {
        const [x1, y1, x2, y2] = det.bbox;
        const color = COLORS[det.class_name] || DEFAULT_COLOR;
        ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        const label = `${det.class_name} ${(det.confidence * 100).toFixed(0)}%`;
        const textW = ctx.measureText(label).width + 8;
        ctx.fillStyle = color; ctx.fillRect(x1, y1 - 22, textW, 22);
        ctx.fillStyle = "#fff"; ctx.font = "13px monospace"; ctx.fillText(label, x1 + 4, y1 - 6);
      });

      // Tracks inside fence
      tracks.filter((t) => t.inside_fence).forEach((t) => {
        const [x1, y1, x2] = t.bbox; const cx = (x1 + x2) / 2;
        ctx.beginPath(); ctx.arc(cx, y1, 6, 0, Math.PI * 2);
        ctx.fillStyle = "#FF0000"; ctx.fill();
        ctx.fillStyle = "#fff"; ctx.font = "bold 11px monospace"; ctx.fillText("!", cx - 3, y1 + 4);
      });
    }, [detections, tracks, fencePoints, width, height]);

    useEffect(() => { draw(); }, [draw]);
    useEffect(() => {
      let raf: number;
      const loop = () => { draw(); raf = requestAnimationFrame(loop); };
      raf = requestAnimationFrame(loop);
      return () => cancelAnimationFrame(raf);
    }, [draw]);

    if (!streaming) {
      if (previewImage) {
        return (
          <div className="relative inline-block max-w-full max-h-full">
            <img src={`data:image/jpeg;base64,${previewImage}`} alt="preview"
              className="max-w-full max-h-[calc(100vh-160px)] rounded block opacity-60" />
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/30 rounded">
              <span className="text-5xl mb-2 opacity-90">?</span>
              <span className="text-sm text-gray-400">点击摄像头或上传视频开始监控</span>
            </div>
          </div>
        );
      }
      return null;
    }

    // Streaming but no frame yet: show loading
    if (!imageSrc) {
      return (
        <div className="relative inline-block max-w-full max-h-full flex items-center justify-center" style={{ width: Math.max(width, 640), height: Math.max(height, 480), minWidth: 320, minHeight: 240 }}>
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 border-3 border-primary-container/30 border-t-primary-container rounded-full animate-spin" />
            <span className="text-sm text-primary-fixed-dim font-medium">模型推理中...</span>
            <span className="text-[10px] text-on-surface-variant">等待首帧画面</span>
          </div>
        </div>
      );
    }

    return (
      <div className="relative inline-block max-w-full max-h-full">
        <img ref={imgRef} src={imageSrc} alt="stream"
          className="max-w-full max-h-[calc(100vh-160px)] rounded block" />
        <canvas ref={canvasRef}
          className="absolute top-0 left-0 w-full h-full pointer-events-none rounded" />
      </div>
    );
  }
);
VideoPanel.displayName = "VideoPanel";
export default VideoPanel;
