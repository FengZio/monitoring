import React, { useState, useEffect, useCallback } from "react";
import type { AlertRecord } from "../types";
import { getAlerts, updateAlertStatus, getAlertClipUrl } from "../services/api";

interface Props { compact?: boolean; }

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: "未处理", color: "border-red-400 text-red-300" },
  processing: { label: "处理中", color: "border-orange-400 text-orange-300" },
  dismissed: { label: "已误报", color: "border-gray-500 text-gray-400" },
  resolved: { label: "已处理", color: "border-green-400 text-green-300" },
};

const AlertHistory: React.FC<Props> = ({ compact }) => {
  const [data, setData] = useState<AlertRecord[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [selected, setSelected] = useState<AlertRecord | null>(null);
  const [handler, setHandler] = useState("");
  const [opinion, setOpinion] = useState("");
  const [newStatus, setNewStatus] = useState("processing");
  const [clipUrl, setClipUrl] = useState("");

  const load = useCallback(() => {
    getAlerts(page, compact ? 15 : 20, statusFilter)
      .then((r) => { setData(r.items); setTotal(r.total); })
      .catch(() => {});
  }, [page, statusFilter, compact]);

  useEffect(() => { load(); }, [load]);

  const handleOpen = (r: AlertRecord) => {
    setSelected(r);
    setHandler(r.handler || "");
    setOpinion(r.opinion || "");
    setNewStatus("processing");
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    if (!selected) return;
    try {
      await updateAlertStatus(selected.id, newStatus, handler, opinion);
      setModalOpen(false);
      load();
    } catch { /* */ }
  };

  return (
    <div>
      {/* Filter */}
      <div className="flex items-center gap-2 mb-2">
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="bg-surface-container border border-outline-variant rounded p-1 text-[10px] text-on-surface-variant">
          <option value="">全部状态</option>
          <option value="pending">未处理</option>
          <option value="processing">处理中</option>
          <option value="dismissed">已误报</option>
          <option value="resolved">已处理</option>
        </select>
        <span className="text-[10px] text-on-surface-variant ml-auto">共 {total} 条</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[10px]">
          <thead className="text-on-surface-variant border-b border-outline-variant/20">
            <tr>
              <th className="py-1 pr-2">ID</th>
              <th className="py-1 pr-2">类型</th>
              <th className="py-1 pr-2">时间</th>
              <th className="py-1 pr-2">状态</th>
              <th className="py-1 pr-2">处理人</th>
              <th className="py-1">操作</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => {
              const st = STATUS_LABELS[r.status] || STATUS_LABELS.pending;
              return (
                <tr key={r.id} className="border-b border-outline-variant/10 hover:bg-surface-variant/20">
                  <td className="py-1.5 pr-2 text-on-surface-variant">#{r.id}</td>
                  <td className="py-1.5 pr-2 text-on-surface">{r.class_name}</td>
                  <td className="py-1.5 pr-2 text-on-surface-variant whitespace-nowrap">{r.timestamp?.replace("T", " ").slice(5, 16)}</td>
                  <td className="py-1.5 pr-2"><span className={`px-1.5 py-0.5 border rounded text-[9px] ${st.color}`}>{st.label}</span></td>
                  <td className="py-1.5 pr-2 text-on-surface-variant">{r.handler || "-"}</td>
                  <td className="py-1.5 flex gap-1">
                    <button onClick={() => handleOpen(r)} className="px-1.5 py-0.5 bg-surface-container border border-outline-variant/30 rounded text-[9px] hover:text-primary transition-colors">处理</button>
                    {r.clip_path && (
                      <button onClick={() => setClipUrl(getAlertClipUrl(r.id))} className="px-1.5 py-0.5 bg-surface-container border border-outline-variant/30 rounded text-[9px] hover:text-primary transition-colors">?</button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {!compact && total > 20 && (
        <div className="flex justify-center gap-2 mt-3">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}
            className="px-2 py-0.5 text-[10px] border border-outline-variant rounded disabled:opacity-30">上一页</button>
          <span className="text-[10px] text-on-surface-variant self-center">{page} / {Math.ceil(total / 20)}</span>
          <button disabled={page >= Math.ceil(total / 20)} onClick={() => setPage(page + 1)}
            className="px-2 py-0.5 text-[10px] border border-outline-variant rounded disabled:opacity-30">下一页</button>
        </div>
      )}

      {/* Clip modal */}
      {clipUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setClipUrl("")}>
          <div className="glass-panel p-4 rounded-xl" onClick={(e) => e.stopPropagation()}>
            <video src={clipUrl} controls className="max-w-lg rounded" autoPlay />
            <button className="mt-2 text-xs text-on-surface-variant hover:text-primary" onClick={() => setClipUrl("")}>关闭</button>
          </div>
        </div>
      )}

      {/* Handle modal */}
      {modalOpen && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setModalOpen(false)}>
          <div className="glass-panel p-6 rounded-xl w-96 space-y-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm text-primary-fixed-dim font-bold">告警处理 #{selected.id}</h3>
            <div>
              <label className="text-[10px] text-on-surface-variant block mb-1">状态</label>
              <select value={newStatus} onChange={(e) => setNewStatus(e.target.value)}
                className="w-full bg-surface-container border border-outline-variant rounded p-2 text-xs text-on-surface">
                <option value="processing">处理中</option>
                <option value="resolved">已处理</option>
                <option value="dismissed">已误报</option>
              </select>
            </div>
            <input value={handler} onChange={(e) => setHandler(e.target.value)}
              className="w-full bg-surface-container border border-outline-variant rounded p-2 text-xs text-on-surface" placeholder="处理人" />
            <textarea value={opinion} onChange={(e) => setOpinion(e.target.value)} rows={3}
              className="w-full bg-surface-container border border-outline-variant rounded p-2 text-xs text-on-surface resize-none" placeholder="处理意见" />
            <div className="flex justify-end gap-2">
              <button onClick={() => setModalOpen(false)} className="px-4 py-1.5 text-xs border border-outline-variant rounded text-on-surface-variant">取消</button>
              <button onClick={handleSubmit} className="px-4 py-1.5 text-xs bg-primary-container/20 border border-primary-container rounded text-primary-container">确认</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AlertHistory;
