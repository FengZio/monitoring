import React, { useState, useEffect } from "react";
import { getConfig, saveConfig } from "../services/api";
import type { ConfigData } from "../types";
import { ALL_CLASSES } from "../types";

interface Props { open: boolean; onClose: () => void; }

const CLASS_LABELS: Record<string, string> = {
  person: "人员", bicycle: "自行车", car: "轿车",
  motorcycle: "摩托车", bus: "巴士", truck: "卡车",
};

const ConfigDialog: React.FC<Props> = ({ open, onClose }) => {
  const [cfg, setCfg] = useState<ConfigData>({
    email_enabled: false, email_smtp_server: "", email_smtp_port: 465,
    email_user: "", email_password: "", email_to: "",
    dingtalk_enabled: false, dingtalk_webhook: "", picgo_key: "",
    alert_classes: ALL_CLASSES,
  });

  useEffect(() => {
    if (open) getConfig().then((d) => setCfg({ ...cfg, ...d, alert_classes: d.alert_classes || ALL_CLASSES })).catch(() => {});
  }, [open]);

  const handleSave = async () => {
    try { await saveConfig(cfg); onClose(); } catch { /* */ }
  };

  const toggleClass = (name: string) => {
    const current = cfg.alert_classes || [];
    setCfg({
      ...cfg,
      alert_classes: current.includes(name)
        ? current.filter((c) => c !== name)
        : [...current, name],
    });
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onClose}>
      <div className="glass-panel p-6 rounded-xl w-[480px] max-h-[80vh] overflow-y-auto space-y-4" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm text-primary-fixed-dim font-bold">系统配置</h3>

        {/* Email */}
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-xs text-on-surface">
            <input type="checkbox" checked={cfg.email_enabled} onChange={(e) => setCfg({ ...cfg, email_enabled: e.target.checked })}
              className="accent-primary-container" /> 启用邮件通知
          </label>
          {cfg.email_enabled && (
            <div className="grid grid-cols-2 gap-2 pl-6">
              <input placeholder="SMTP 服务器" value={cfg.email_smtp_server} onChange={(e) => setCfg({ ...cfg, email_smtp_server: e.target.value })}
                className="bg-surface-container border border-outline-variant rounded p-1.5 text-xs text-on-surface" />
              <input type="number" placeholder="端口" value={cfg.email_smtp_port} onChange={(e) => setCfg({ ...cfg, email_smtp_port: +e.target.value })}
                className="bg-surface-container border border-outline-variant rounded p-1.5 text-xs text-on-surface" />
              <input placeholder="用户名" value={cfg.email_user} onChange={(e) => setCfg({ ...cfg, email_user: e.target.value })}
                className="bg-surface-container border border-outline-variant rounded p-1.5 text-xs text-on-surface" />
              <input type="password" placeholder="密码" value={cfg.email_password} onChange={(e) => setCfg({ ...cfg, email_password: e.target.value })}
                className="bg-surface-container border border-outline-variant rounded p-1.5 text-xs text-on-surface" />
              <input placeholder="收件人 (逗号分隔)" value={cfg.email_to} onChange={(e) => setCfg({ ...cfg, email_to: e.target.value })}
                className="col-span-2 bg-surface-container border border-outline-variant rounded p-1.5 text-xs text-on-surface" />
            </div>
          )}
        </div>

        {/* DingTalk */}
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-xs text-on-surface">
            <input type="checkbox" checked={cfg.dingtalk_enabled} onChange={(e) => setCfg({ ...cfg, dingtalk_enabled: e.target.checked })}
              className="accent-primary-container" /> 启用钉钉通知
          </label>
          {cfg.dingtalk_enabled && (
            <>
            <input placeholder="Webhook URL" value={cfg.dingtalk_webhook} onChange={(e) => setCfg({ ...cfg, dingtalk_webhook: e.target.value })}
              className="w-full bg-surface-container border border-outline-variant rounded p-1.5 text-xs text-on-surface ml-6" />
            <input placeholder="Picgo API Key" value={cfg.picgo_key || ""} onChange={(e) => setCfg({ ...cfg, picgo_key: e.target.value })}
              className="w-full bg-surface-container border border-outline-variant rounded p-1.5 text-xs text-on-surface ml-6 mt-2" />
            </>
          )}
        </div>

        {/* Alert Class Filter */}
        <div className="space-y-2">
          <h4 className="text-xs text-on-surface font-medium">告警目标类别</h4>
          <p className="text-[10px] text-on-surface-variant">仅勾选的类别触发围栏告警</p>
          <div className="flex flex-wrap gap-2">
            {ALL_CLASSES.map((name) => (
              <label key={name} className="flex items-center gap-1.5 text-xs text-on-surface cursor-pointer">
                <input type="checkbox" checked={(cfg.alert_classes || []).includes(name)}
                  onChange={() => toggleClass(name)}
                  className="accent-primary-container" />
                {CLASS_LABELS[name] || name}
              </label>
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="px-4 py-1.5 text-xs border border-outline-variant rounded text-on-surface-variant hover:text-on-surface">取消</button>
          <button onClick={handleSave} className="px-4 py-1.5 text-xs bg-primary-container/20 border border-primary-container rounded text-primary-container">保存</button>
        </div>
      </div>
    </div>
  );
};

export default ConfigDialog;