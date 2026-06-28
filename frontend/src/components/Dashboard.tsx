import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import {
  getStatsOverview, getStatsDaily, getStatsHourly, getClassDistribution, getHeatmap,
  getAlerts, listSources,
} from "../services/api";
import type { StatsOverview, DailyStat, HourlyStat, ClassDistItem, HeatmapData, AlertRecord } from "../types";

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [overview, setOverview] = useState<StatsOverview | null>(null);
  const [daily, setDaily] = useState<DailyStat[]>([]);
  const [hourly, setHourly] = useState<HourlyStat[]>([]);
  const [classDist, setClassDist] = useState<ClassDistItem[]>([]);
  const [heatmap, setHeatmap] = useState<HeatmapData | null>(null);
  const [recentAlerts, setRecentAlerts] = useState<AlertRecord[]>([]);
  const [onlineCount, setOnlineCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [chartMode, setChartMode] = useState<"daily" | "hourly">("daily");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, dl, hr, cd, hm, al, srcs] = await Promise.all([
        getStatsOverview(), getStatsDaily(7), getStatsHourly(),
        getClassDistribution(), getHeatmap(), getAlerts(1, 10), listSources(),
      ]);
      setOverview(ov);
      setDaily(dl.daily);
      setHourly(hr.hourly);
      setClassDist(cd.distribution);
      setHeatmap(hm);
      setRecentAlerts(al.items);
      setOnlineCount(srcs.sources.filter((s: any) => s.ready).length);
    } catch { /* */ }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  const trendOption = chartMode === "daily" ? {
    backgroundColor: "transparent", tooltip: { trigger: "axis" },
    textStyle: { color: "#b9cacb", fontSize: 11 },
    xAxis: { type: "category", data: daily.map((d) => d.date.slice(5)), axisLabel: { color: "#849495", fontSize: 10 }, axisLine: { lineStyle: { color: "#3a494b" } } },
    yAxis: { type: "value", axisLabel: { color: "#849495", fontSize: 10 }, splitLine: { lineStyle: { color: "#2e3445" } } },
    series: [{ data: daily.map((d) => d.count), type: "line", smooth: true, areaStyle: { color: "rgba(0,219,231,0.12)" }, lineStyle: { color: "#00dbe7" }, itemStyle: { color: "#00dbe7" } }],
    grid: { left: 40, right: 20, top: 15, bottom: 25 },
  } : {
    backgroundColor: "transparent", tooltip: { trigger: "axis" },
    textStyle: { color: "#b9cacb", fontSize: 11 },
    xAxis: { type: "category", data: hourly.map((h) => `${h.hour}h`), axisLabel: { color: "#849495", fontSize: 10 }, axisLine: { lineStyle: { color: "#3a494b" } } },
    yAxis: { type: "value", axisLabel: { color: "#849495", fontSize: 10 }, splitLine: { lineStyle: { color: "#2e3445" } } },
    series: [{ data: hourly.map((h) => h.count), type: "bar", itemStyle: { color: "#d1bcff", borderRadius: [4, 4, 0, 0] } }],
    grid: { left: 40, right: 20, top: 15, bottom: 25 },
  };

  const pieOption = {
    backgroundColor: "transparent", tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    textStyle: { color: "#b9cacb" },
    series: [{
      type: "pie", radius: ["45%", "75%"], center: ["50%", "55%"],
      data: classDist.map((d) => ({ name: d.name, value: d.count })),
      label: { color: "#b9cacb", fontSize: 10 },
      emphasis: { label: { fontSize: 14, fontWeight: "bold" } },
    }],
  };

  const heatmapOption = heatmap ? {
    backgroundColor: "transparent", tooltip: { trigger: "item" },
    textStyle: { color: "#b9cacb" },
    xAxis: { type: "value", axisLabel: { color: "#849495", fontSize: 9 }, splitLine: { show: false } },
    yAxis: { type: "value", axisLabel: { color: "#849495", fontSize: 9 }, splitLine: { show: false }, inverse: true },
    visualMap: { min: 0, max: Math.max(3, ...heatmap.points.map(() => 1)), calculable: true, orient: "horizontal", left: "center", bottom: 0, inRange: { color: ["#0c1322", "#ff3333", "#ff0000", "#990000"] }, textStyle: { color: "#849495", fontSize: 9 } },
    series: [{ type: "heatmap", data: heatmap.points.map((p) => [p[0], p[1], 1]), emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.5)" } } }],
    grid: { left: 50, right: 20, top: 15, bottom: 50 },
  } : null;

  return (
    <div className="dark bg-background text-on-background min-h-screen flex flex-col overflow-auto font-body">
      {/* Header */}
      <header className="sticky top-0 z-50 flex items-center justify-between px-8 h-16 bg-background/40 backdrop-blur-xl border-b border-outline-variant/30">
        <div className="flex items-center gap-6">
          <button onClick={() => navigate("/")} className="material-symbols-outlined text-on-surface-variant hover:text-primary transition-colors">arrow_back</button>
          <span className="font-display text-2xl text-primary-fixed-dim tracking-tighter">宙斯盾监控看板</span>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={load} className="material-symbols-outlined text-on-surface-variant hover:text-primary transition-colors">refresh</button>
          <span className="text-[10px] text-on-surface-variant">自动刷新 30s</span>
        </div>
      </header>

      <div className="p-6 space-y-5 max-w-7xl mx-auto w-full">
        {/* KPI Cards */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { title: "今日告警数", value: overview?.total_today || 0, icon: "notifications_active", border: "border-l-2 border-error", color: "text-error" },
            { title: "在线摄像头", value: onlineCount, icon: "videocam", border: "border-l-2 border-primary-container", color: "text-primary-fixed-dim" },
            { title: "未处理告警", value: overview?.pending || 0, icon: "pending_actions", border: "border-l-2 border-secondary", color: "text-secondary" },
            { title: "处理率", value: `${((overview?.handle_rate || 0) * 100).toFixed(1)}%`, icon: "check_circle", border: "border-l-2 border-tertiary-fixed-dim", color: "text-tertiary-fixed-dim" },
          ].map((item, i) => (
            <div key={i} className={`glass-panel p-4 rounded-xl flex items-center gap-4 ${item.border}`}>
              <span className={`material-symbols-outlined text-3xl ${item.color}`}>{item.icon}</span>
              <div>
                <p className="text-on-surface-variant text-[10px] uppercase">{item.title}</p>
                <p className={`text-2xl font-bold ${item.color}`}>{item.value}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Charts row 1 */}
        <div className="grid grid-cols-2 gap-4">
          <div className="glass-panel p-5 rounded-xl flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs text-on-surface-variant uppercase tracking-widest">告警趋势</h3>
              <div className="flex bg-surface-container rounded p-0.5">
                <button onClick={() => setChartMode("daily")}
                  className={`px-2 py-0.5 text-[10px] rounded ${chartMode === "daily" ? "bg-primary-container text-on-primary-container" : "text-on-surface-variant"}`}>7天</button>
                <button onClick={() => setChartMode("hourly")}
                  className={`px-2 py-0.5 text-[10px] rounded ${chartMode === "hourly" ? "bg-primary-container text-on-primary-container" : "text-on-surface-variant"}`}>24h</button>
              </div>
            </div>
            <ReactECharts option={trendOption} style={{ height: 260 }} />
          </div>

          <div className="glass-panel p-5 rounded-xl flex flex-col">
            <h3 className="text-xs text-on-surface-variant uppercase tracking-widest mb-3">目标类别分布</h3>
            <div className="flex items-center justify-around flex-1">
              <ReactECharts option={pieOption} style={{ height: 260, width: "100%" }} />
            </div>
          </div>
        </div>

        {/* Charts row 2 */}
        <div className="grid grid-cols-2 gap-4">
          <div className="glass-panel p-5 rounded-xl flex flex-col">
            <h3 className="text-xs text-on-surface-variant uppercase tracking-widest mb-3">围栏闯入热力图</h3>
            {heatmapOption ? (
              <ReactECharts option={heatmapOption} style={{ height: 260 }} />
            ) : (
              <div className="flex-1 flex items-center justify-center text-on-surface-variant text-xs">暂无热力图数据</div>
            )}
          </div>

          <div className="glass-panel p-5 rounded-xl flex flex-col">
            <h3 className="text-xs text-on-surface-variant uppercase tracking-widest mb-3">安全防御等级</h3>
            <div className="flex-1 flex flex-col items-center justify-center gap-4">
              <div className="relative w-32 h-32 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90">
                  <circle className="text-surface-container-high" cx="64" cy="64" fill="transparent" r="56" stroke="currentColor" strokeWidth="6" />
                  <circle className="text-primary-container" cx="64" cy="64" fill="transparent" r="56" stroke="currentColor"
                    strokeDasharray="352" strokeDashoffset={352 * (1 - (overview?.handle_rate || 0))} strokeWidth="6" />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl text-primary-fixed-dim font-bold">{((overview?.handle_rate || 0) * 100).toFixed(0)}%</span>
                  <span className="text-[10px] text-on-surface-variant">处理率</span>
                </div>
              </div>
              <div className="flex gap-6 text-center">
                <div><p className="text-[10px] text-on-surface-variant">威胁等级</p><p className="text-xs text-primary font-bold">低风险</p></div>
                <div><p className="text-[10px] text-on-surface-variant">数据加密</p><p className="text-xs text-primary font-bold">TLS 1.3</p></div>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Alerts */}
        <div className="glass-panel p-5 rounded-xl">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs text-on-surface-variant uppercase tracking-widest">近期告警日志</h3>
            <span className="text-[10px] text-primary-fixed-dim cursor-pointer hover:underline" onClick={() => navigate("/")}>返回监控</span>
          </div>
          <div className="space-y-2">
            {recentAlerts.map((r) => (
              <div key={r.id} className="p-3 bg-surface-container-high border-l-2 border-error rounded-r flex gap-3">
                <span className="material-symbols-outlined text-error text-[20px]">dangerous</span>
                <div className="flex-1">
                  <p className="text-xs text-on-surface font-bold">{r.class_name} - #{r.id}</p>
                  <p className="text-[9px] text-on-surface-variant mt-1">{r.timestamp?.replace("T", " ").slice(0, 16)} · {r.status} · handler: {r.handler || "-"}</p>
                </div>
                <span className="text-[10px] text-on-surface-variant">{(r.confidence * 100).toFixed(0)}%</span>
              </div>
            ))}
            {recentAlerts.length === 0 && <div className="text-center text-on-surface-variant text-xs py-6">暂无告警记录</div>}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="flex justify-between items-center px-8 py-2 bg-surface-container-lowest border-t border-outline-variant/20 mt-auto">
        <div className="flex items-center gap-4">
          <span className="text-xs text-secondary">运行状态：正常</span>
          <span className="text-[10px] text-on-surface-variant">© 2026 宙斯盾监控系统</span>
        </div>
        <div className="flex gap-6">
          <a className="text-[10px] text-on-surface-variant hover:text-primary cursor-pointer" onClick={() => navigate("/")}>监控首页</a>
          <a className="text-[10px] text-on-surface-variant hover:text-primary cursor-pointer">终端访问</a>
          <a className="text-[10px] text-on-surface-variant hover:text-primary cursor-pointer">API 文档</a>
        </div>
      </footer>
    </div>
  );
};

export default Dashboard;
