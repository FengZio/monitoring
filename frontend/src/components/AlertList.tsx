import React, { useState } from "react";
import type { AlertInfo, AlertRecord } from "../types";
import { updateAlertStatus, getAlertClipUrl } from "../services/api";

interface Props { alerts: AlertInfo[]; compact?: boolean; }

const STATUS_COLORS: Record<string, string> = {
  pending: "border-red-400 text-red-300",
  processing: "border-orange-400 text-orange-300",
  dismissed: "border-gray-500 text-gray-400",
  resolved: "border-green-400 text-green-300",
};

const AlertList: React.FC<Props> = ({ alerts, compact }) => {
  const [modalOpen, setModalOpen] = useState(false);
  const [handler, setHandler] = useState("");
  const [opinion, setOpinion] = useState("");
  const [status, setStatus] = useState("processing");
  const [clipUrl, setClipUrl] = useState("");
  const [selectedAlert, setSelectedAlert] = useState<any>(null);

  const handleOpen = (alert: any) => {
    setSelectedAlert(alert);
    setHandler("");
    setOpinion("");
    setStatus("processing");
    setClipUrl("");
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    if (!selectedAlert?.id) return;
    try {
      await updateAlertStatus(selectedAlert.id, status, handler, opinion);
      setModalOpen(false);
    } catch { /* */ }
  };

  if (compact) {
    return (
      <div className="space-y-1">
        {alerts.slice(-50).reverse().map((a: any, i) => (
          <div key={i} className="p-2 bg-error-container/10 border-l-2 border-error rounded-r flex gap-2 cursor-pointer hover:bg-error-container/20 transition-colors" onClick={() => handleOpen(a)}>
            <span className="material-symbols-outlined text-error text-[16px]">dangerous</span>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] text-on-error-container font-bold">{a.class_name} #{a.track_id}</p>
              <p className="text-[9px] text-on-surface-variant mt-0.5">{(a.confidence * 100).toFixed(0)}%</p>
            </div>
            {a.id && (
              <span className="material-symbols-outlined text-on-surface-variant text-[14px] cursor-pointer"
                onClick={(e) => { e.stopPropagation(); setClipUrl(getAlertClipUrl(a.id)); }}
                title="查看录像">
                play_circle
              </span>
            )}
          </div>
        ))}
        {alerts.length === 0 && <div className="text-center text-on-surface-variant text-[10px] py-4">暂无实时告警</div>}

        {/* Clip video popover */}
        {clipUrl && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setClipUrl("")}>
            <div className="glass-panel p-4 rounded-xl max-w-lg" onClick={(e) => e.stopPropagation()}>
              <video src={clipUrl} controls className="w-full rounded" autoPlay />
              <button className="mt-2 text-xs text-on-surface-variant hover:text-primary transition-colors" onClick={() => setClipUrl("")}>关闭</button>
            </div>
          </div>
        )}

        {/* Handle Modal */}
        {modalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setModalOpen(false)}>
            <div className="glass-panel p-6 rounded-xl w-96 space-y-4" onClick={(e) => e.stopPropagation()}>
              <h3 className="text-sm text-primary-fixed-dim font-bold">告警处理</h3>
              <div>
                <label className="text-[10px] text-on-surface-variant block mb-1">状态</label>
                <select value={status} onChange={(e) => setStatus(e.target.value)}
                  className="w-full bg-surface-container border border-outline-variant rounded p-2 text-xs text-on-surface">
                  <option value="processing">处理中</option>
                  <option value="resolved">已处理</option>
                  <option value="dismissed">已误报</option>
                </select>
              </div>
              <div>
                <label className="text-[10px] text-on-surface-variant block mb-1">处理人</label>
                <input value={handler} onChange={(e) => setHandler(e.target.value)}
                  className="w-full bg-surface-container border border-outline-variant rounded p-2 text-xs text-on-surface" placeholder="输入处理人姓名" />
              </div>
              <div>
                <label className="text-[10px] text-on-surface-variant block mb-1">处理意见</label>
                <textarea value={opinion} onChange={(e) => setOpinion(e.target.value)} rows={3}
                  className="w-full bg-surface-container border border-outline-variant rounded p-2 text-xs text-on-surface resize-none" placeholder="输入处理意见" />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setModalOpen(false)} className="px-4 py-1.5 text-xs border border-outline-variant rounded text-on-surface-variant hover:text-on-surface transition-colors">取消</button>
                <button onClick={handleSubmit} className="px-4 py-1.5 text-xs bg-primary-container/20 border border-primary-container rounded text-primary-container hover:bg-primary-container/30 transition-colors">确认</button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Non-compact: used in right panel
  return (
    <div className="space-y-2">
      {alerts.slice(-50).reverse().map((a: any, i) => (
        <div key={i} className="p-2 bg-error-container/10 border-l-2 border-error rounded-r flex gap-2">
          <span className="material-symbols-outlined text-error text-[16px]">dangerous</span>
          <div className="min-w-0 flex-1">
            <p className="text-xs text-on-error-container font-bold">{a.class_name} #{a.track_id}</p>
            <p className="text-[9px] text-on-surface-variant mt-0.5">{(a.confidence * 100).toFixed(0)}% confidence</p>
          </div>
        </div>
      ))}
    </div>
  );
};

export default AlertList;
