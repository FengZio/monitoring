import React, { useState } from "react";

interface Props {
  open: boolean;
  pixelPoints: [number, number][];
  onOk: (worldPoints: [number, number][]) => void;
  onCancel: () => void;
}

const CalibrationDialog: React.FC<Props> = ({ open, pixelPoints, onOk, onCancel }) => {
  const [worldPoints, setWorldPoints] = useState<string[]>(["", "", "", ""]);

  const handleOk = () => {
    const pts: [number, number][] = [];
    for (let i = 0; i < 4; i++) {
      const parts = worldPoints[i].split(",").map(Number);
      if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
        pts.push([parts[0], parts[1]]);
      } else return;
    }
    onOk(pts);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onCancel}>
      <div className="glass-panel p-6 rounded-xl w-[400px] space-y-4" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm text-primary-fixed-dim font-bold">空间校准 - 输入世界坐标</h3>
        <p className="text-[10px] text-on-surface-variant">为画面上标定的 4 个点输入对应的世界坐标 (x, y 米)</p>
        {pixelPoints.map((pp, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="text-[10px] text-on-surface-variant w-12">点 {i + 1}</span>
            <span className="text-[10px] text-on-surface-variant">像素({pp[0].toFixed(0)}, {pp[1].toFixed(0)})</span>
            <span className="text-on-surface-variant">?</span>
            <input
              placeholder="x, y (如: 10.5, 20.0)"
              value={worldPoints[i]}
              onChange={(e) => {
                const v = [...worldPoints];
                v[i] = e.target.value;
                setWorldPoints(v);
              }}
              className="flex-1 bg-surface-container border border-outline-variant rounded p-1.5 text-xs text-on-surface"
            />
          </div>
        ))}
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onCancel} className="px-4 py-1.5 text-xs border border-outline-variant rounded text-on-surface-variant">取消</button>
          <button onClick={handleOk} className="px-4 py-1.5 text-xs bg-primary-container/20 border border-primary-container rounded text-primary-container">确认校准</button>
        </div>
      </div>
    </div>
  );
};

export default CalibrationDialog;
