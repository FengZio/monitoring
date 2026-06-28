import React, { useState, useRef, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import type { AlertInfo, WSMessage, VideoSource } from "./types";
import { useWS } from "./hooks/useWS";
import {
  getFence, saveFence, clearFence,
  addWebcamSource, addFileSource, removeSource, listSources,
  uploadVideo, listVideos, previewWebcam, previewFile,
  getAlerts,
} from "./services/api";
import VideoPanel, { type VideoPanelHandle } from "./components/VideoPanel";
import FenceCanvas from "./components/FenceCanvas";
import AlertList from "./components/AlertList";
import AlertHistory from "./components/AlertHistory";
import ConfigDialog from "./components/ConfigDialog";
import type { AlertRecord } from "./types";

const COLORS = ["#00dbe7", "#ff6384", "#ffcd56", "#4bc0c0", "#9966ff", "#ff9f40", "#c9cbcf"];

const PieChart: React.FC<{ data: { name: string; value: number }[] }> = ({ data }) => {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  let cumAngle = -Math.PI / 2;
  const cx = 70, cy = 70, outerR = 55, innerR = 30;

  if (data.length === 0) {
    return (
      <div className="glass-panel rounded-xl p-3 flex flex-col">
        <h3 className="text-[10px] text-on-surface-variant uppercase tracking-wider mb-1">实时检测分布</h3>
        <div className="flex-1 flex items-center justify-center text-[10px] text-on-surface-variant/50">等待检测数据...</div>
      </div>
    );
  }

  return (
    <div className="glass-panel rounded-xl p-3 flex flex-col">
      <h3 className="text-[10px] text-on-surface-variant uppercase tracking-wider mb-1">实时检测分布</h3>
      <div className="flex-1 flex items-center gap-4">
        {/* Donut chart - left */}
        <svg viewBox="0 0 140 140" className="w-[90px] h-[90px] flex-shrink-0">
          {data.map((d, i) => {
            const angle = (d.value / total) * Math.PI * 2;
            const startAngle = cumAngle;
            cumAngle += angle;
            const x1 = cx + outerR * Math.cos(startAngle);
            const y1 = cy + outerR * Math.sin(startAngle);
            const x2 = cx + outerR * Math.cos(startAngle + angle);
            const y2 = cy + outerR * Math.sin(startAngle + angle);
            const ix1 = cx + innerR * Math.cos(startAngle);
            const iy1 = cy + innerR * Math.sin(startAngle);
            const ix2 = cx + innerR * Math.cos(startAngle + angle);
            const iy2 = cy + innerR * Math.sin(startAngle + angle);
            const large = angle > Math.PI ? 1 : 0;
            const color = COLORS[i % COLORS.length];
            const path = `M ${ix1} ${iy1} L ${x1} ${y1} A ${outerR} ${outerR} 0 ${large} 1 ${x2} ${y2} L ${ix2} ${iy2} A ${innerR} ${innerR} 0 ${large} 0 ${ix1} ${iy1} Z`;
            return <path key={d.name} d={path} fill={color} opacity={0.9} stroke="#0c1322" strokeWidth={1.5} />;
          })}
          <text x="70" y="66" textAnchor="middle" fill="#b9cacb" fontSize="14" fontWeight="bold">{total}</text>
          <text x="70" y="80" textAnchor="middle" fill="#849495" fontSize="8">total</text>
        </svg>
        {/* Legend - right */}
        <div className="flex flex-col gap-1.5 flex-1 min-w-0">
          {data.slice(0, 6).map((d, i) => (
            <div key={d.name} className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
              <span className="text-[10px] text-on-surface font-medium truncate">{d.name}</span>
              <span className="text-[9px] text-on-surface-variant ml-auto tabular-nums">{d.value} ({((d.value / total) * 100).toFixed(0)}%)</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const App: React.FC = () => {
  const navigate = useNavigate();

  // Video state
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [videoSize, setVideoSize] = useState({ width: 0, height: 0 });
  const videoPanelRef = useRef<VideoPanelHandle>(null);

  // Sources
  const [sources, setSources] = useState<VideoSource[]>([]);
  const [activeSourceId, setActiveSourceId] = useState("");
  const [sourceTab, setSourceTab] = useState<"sources" | "alerts" | "history">("sources");

  // Fence
  const [fencePoints, setFencePoints] = useState<[number, number][]>([]);
  const [fenceEditing, setFenceEditing] = useState(false);
  const hasFence = fencePoints.length >= 3;

  // Alerts
  const [alerts, setAlerts] = useState<AlertInfo[]>([]);
  const alertsRef = useRef<AlertInfo[]>([]);
  const [recentHistory, setRecentHistory] = useState<AlertRecord[]>([]);
  const [chartDaily, setChartDaily] = useState<{date: string; count: number}[]>([]);
  const [liveClasses, setLiveClasses] = useState<{name: string; value: number}[]>([]);
  const [videoFiles, setVideoFiles] = useState<{filename: string; size: number}[]>([]);

  // UI
  const [configOpen, setConfigOpen] = useState(false);
  const [orbActive, setOrbActive] = useState(false);

  // ---- WebSocket ----
  const handleMessage = useCallback((msg: WSMessage) => {
    if (msg.type !== "frame" || !msg.image) return;
    setImageSrc(`data:image/jpeg;base64,${msg.image}`);
    setVideoSize({ width: msg.width, height: msg.height });
    if (msg.orb_tracking && msg.fence_pixels && msg.fence_pixels.length >= 3 && !fenceEditing ) {
      setFencePoints(msg.fence_pixels);
    }
    setOrbActive(msg.orb_tracking);
    if (msg.alerts && msg.alerts.length > 0) {
      const newAlerts = [...alertsRef.current, ...msg.alerts];
      alertsRef.current = newAlerts;
      setAlerts(newAlerts);
    }
  }, [fenceEditing]);

  const { lastMessage, connected, connect, disconnect } = useWS(handleMessage);

  // Live class distribution from lastMessage (watches every frame)
  useEffect(() => {
    const msg = lastMessage;
    if (msg?.detections && msg.detections.length > 0) {
      const counts: Record<string, number> = {};
      for (const d of msg.detections) {
        counts[d.class_name] = (counts[d.class_name] || 0) + 1;
      }
      setLiveClasses(
        Object.entries(counts)
          .map(([name, value]) => ({ name, value }))
          .sort((a, b) => b.value - a.value)
      );
    }
  }, [lastMessage]);

  // ---- Load sources periodically ----
  useEffect(() => {
    const load = () => listSources().then((d) => setSources(d.sources || [])).catch(() => {});
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  // ---- Load history ----
  useEffect(() => {
    getAlerts(1, 10).then((r) => setRecentHistory(r.items)).catch(() => {});
  }, [alerts]);

  useEffect(() => {
    listVideos().then((d) => setVideoFiles(d.videos || [])).catch(() => {});
  }, []);

  useEffect(() => {
    const load = () => {
      fetch("/api/stats/daily?days=7").then((r) => r.json()).then((d) => setChartDaily(d.daily || [])).catch(() => {});
    };
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);

  // ---- Load fence on source change ----
  useEffect(() => {
    getFence(activeSourceId || "default").then((d) => {
      setFencePoints(d.points || []);
    }).catch(() => {});
  }, [activeSourceId]);

  // ---- Source actions ----
  const handleSelectSource = (sid: string) => {
    if (sid === activeSourceId) return;
    disconnect();
    setActiveSourceId(sid);
    connect(sid);
    setStreaming(true);
    setPreviewImage(null);
  };

  const handleAddWebcam = async () => {
    try {
      const res = await addWebcamSource(0);
      setActiveSourceId(res.source_id);
      connect(res.source_id);
      setStreaming(true);
      setPreviewImage(null);
    } catch { /* */ }
  };

  const handleAddFile = async (filename: string) => {
    try {
      const data = await previewFile(filename);
      if (data.frame) setPreviewImage(data.frame);
      const res = await addFileSource(filename);
      setTimeout(() => {
        setActiveSourceId(res.source_id);
        connect(res.source_id);
        setStreaming(true);
        setPreviewImage(null);
      }, 800);
      setVideoFiles((prev) => {
        if (!prev.find((v) => v.filename === filename)) {
          return [{ filename, size: 0 }, ...prev];
        }
        return prev;
      });
    } catch { /* */ }
  };

  const handleRemoveSource = async () => {
    if (!activeSourceId) return;
    try {
      await removeSource(activeSourceId);
      disconnect();
      setActiveSourceId("");
      setStreaming(false);
    } catch { /* */ }
  };

  const handlePlayFile = async (filename: string) => {
    try {
      const data = await previewFile(filename);
      if (data.frame) setPreviewImage(data.frame);
      const res = await addFileSource(filename);
      setTimeout(() => {
        setActiveSourceId(res.source_id);
        connect(res.source_id);
        setStreaming(true);
        setPreviewImage(null);
      }, 800);
    } catch { /* */ }
  };

  const handlePreviewWebcam = async () => {
    try {
      const d = await previewWebcam(0);
      if (d.frame) setPreviewImage(d.frame);
    } catch { /* */ }
  };

  const handlePreviewFile = async (filename: string) => {
    try {
      const d = await previewFile(filename);
      if (d.frame) setPreviewImage(d.frame);
    } catch { /* */ }
  };

  // ---- Fence actions ----
  const handleFenceSave = () => saveFence(fencePoints, activeSourceId || "default")
    .then(() => setFenceEditing(false)).catch(() => {});
  const handleFenceClear = () => clearFence(activeSourceId || "default")
    .then(() => { setFencePoints([]); setFenceEditing(false); }).catch(() => {});


  const onlineCount = sources.filter((s) => s.ready).length;

  return (
    <div className="dark bg-background text-on-background h-screen flex flex-col overflow-hidden font-body">
      {/* ===== HEADER ===== */}
      <header className="z-50 flex items-center justify-between px-8 h-16 bg-background/40 backdrop-blur-xl border-b border-outline-variant/30 shadow-sm">
        <div className="flex items-center gap-12">
          <span
            className="font-display text-2xl text-primary-fixed-dim tracking-tighter cursor-pointer"
            onClick={() => navigate("/")}
          >
            宙斯盾监控看板
          </span>
        </div>
        <nav className="hidden xl:flex gap-8 items-center h-full">
          <a className="text-primary-fixed-dim border-b-2 border-primary-fixed-dim pb-1 font-bold text-xs uppercase tracking-wider text-glow" href="#">概览</a>
          <a className="text-on-surface-variant font-medium text-xs uppercase tracking-wider hover:text-primary transition-colors cursor-pointer" onClick={() => navigate("/dashboard")}>统计</a>
          <a className="text-on-surface-variant font-medium text-xs uppercase tracking-wider hover:text-primary transition-colors cursor-pointer" onClick={() => setConfigOpen(true)}>配置</a>
        </nav>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <button className="material-symbols-outlined text-on-surface-variant hover:text-primary transition-colors">schedule</button>
            <button className="material-symbols-outlined text-on-surface-variant hover:text-primary transition-colors">cloud</button>
            <div className="relative">
              <button className="material-symbols-outlined text-on-surface-variant hover:text-primary transition-colors">notifications_active</button>
              {alerts.length > 0 && <span className="absolute -top-1 -right-1 w-2 h-2 bg-primary-container rounded-full animate-pulse" />}
            </div>
            <div className="w-8 h-8 rounded-full border border-primary-fixed-dim overflow-hidden bg-surface-container ml-2 flex items-center justify-center">
              <span className="material-symbols-outlined text-primary-fixed-dim text-lg">person</span>
            </div>
          </div>
        </div>
      </header>

      {/* ===== MAIN ===== */}
      <main className="flex flex-1 overflow-hidden">
        {/* LEFT SIDEBAR - Sources */}
        <aside className="w-72 flex flex-col border-r border-outline-variant/20 bg-surface-container-low/40 backdrop-blur-2xl">
          <div className="p-6 border-b border-outline-variant/10">
            <h2 className="font-headline text-sm text-primary uppercase tracking-wider">视频源线路</h2>
            <p className="text-[10px] text-on-surface-variant uppercase tracking-wider mt-1">源节点切换</p>
          </div>

          {/* Tab toggle */}
          <div className="flex border-b border-outline-variant/10">
            {(["sources", "alerts", "history"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setSourceTab(t)}
                className={`flex-1 py-2 text-[10px] uppercase tracking-wider font-medium transition-colors ${
                  sourceTab === t
                    ? "text-primary-fixed-dim border-b-2 border-primary-fixed-dim"
                    : "text-on-surface-variant hover:text-on-surface"
                }`}
              >
                {t === "sources" ? "源节点" : t === "alerts" ? `告警(${alerts.length})` : "历史"}
              </button>
            ))}
          </div>

          {sourceTab === "sources" && (
            <div className="flex-1 custom-scrollbar p-2 space-y-1">
              {/* Add source buttons */}
              <div className="flex gap-1 mb-3">
                <button
                  onClick={handleAddWebcam}
                  className="flex-1 py-1.5 text-[10px] bg-primary-container/10 border border-primary-container/30 rounded text-primary-container hover:bg-primary-container/20 transition-colors uppercase tracking-wider"
                >
                  + 摄像头
                </button>
                <label className="flex-1 py-1.5 text-[10px] bg-secondary/10 border border-secondary/30 rounded text-secondary hover:bg-secondary/20 transition-colors uppercase tracking-wider text-center cursor-pointer">
                  + 上传
                  <input type="file" accept="video/*" className="hidden" onChange={async (e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      try {
                        const res = await uploadVideo(f);
                        handleAddFile(res.filename);
                      } catch { /* */ }
                    }
                  }} />
                </label>
              </div>

              {/* Existing video files */}
              {videoFiles.length > 0 && (
                <div className="mb-2">
                  <p className="text-[9px] text-on-surface-variant uppercase tracking-wider mb-1 px-1">已上传视频</p>
                  {videoFiles.map((vf) => (
                    <div
                      key={vf.filename}
                      onClick={() => handlePlayFile(vf.filename)}
                      className="p-2 flex items-center gap-2 cursor-pointer hover:bg-surface-variant/30 transition-colors rounded text-[10px] text-on-surface-variant hover:text-on-surface group"
                    >
                      <span className="material-symbols-outlined text-[14px] text-secondary group-hover:text-primary-fixed-dim transition-colors">movie</span>
                      <span className="flex-1 truncate">{vf.filename}</span>
                      <span className="material-symbols-outlined text-[14px] opacity-0 group-hover:opacity-100 transition-opacity text-primary-fixed-dim">play_arrow</span>
                    </div>
                  ))}
                </div>
              )}

              {sources.map((s) => (
                <div
                  key={s.source_id}
                  onClick={() => handleSelectSource(s.source_id)}
                  className={`p-3 flex items-center justify-between cursor-pointer transition-colors rounded ${
                    s.source_id === activeSourceId
                      ? "bg-secondary-container/20 border-r-4 border-primary-fixed-dim"
                      : "hover:bg-surface-variant/30"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-primary-fixed-dim text-[20px]">videocam</span>
                    <span className={`text-xs uppercase ${
                      s.source_id === activeSourceId ? "text-primary" : "text-on-surface-variant"
                    }`}>
                      {s.type === "webcam" ? "摄像头" : "视频"} {s.source_id.slice(0, 6)}
                    </span>
                  </div>
                  <span className={`w-2 h-2 rounded-full ${
                    s.ready ? "bg-primary-container pulse-indicator" : "bg-primary-container opacity-40"
                  }`} />
                </div>
              ))}
              {sources.length === 0 && (
                <div className="p-6 text-center text-on-surface-variant text-xs">
                  <span className="material-symbols-outlined text-4xl mb-2 block opacity-30">videocam_off</span>
                  点击上方按钮添加视频源
                </div>
              )}

              {activeSourceId && (
                <div className="mt-3 p-3 bg-surface-container rounded border border-outline-variant/20 space-y-1">
                  <button
                    onClick={handleRemoveSource}
                    className="w-full py-1.5 text-[10px] bg-error/10 border border-error/30 rounded text-error hover:bg-error/20 transition-colors uppercase tracking-wider"
                  >
                    移除当前源
                  </button>
                </div>
              )}
            </div>
          )}

          {sourceTab === "alerts" && (
            <div className="flex-1 custom-scrollbar p-2">
              <AlertList alerts={alerts} compact />
            </div>
          )}

          {sourceTab === "history" && (
            <div className="flex-1 custom-scrollbar p-2">
              <AlertHistory compact />
            </div>
          )}
        </aside>

        {/* CENTER - Video + Overlay */}
        <section className="flex-1 flex flex-col gap-3 p-3 overflow-hidden">
          {/* Video area */}
          <div className="glass-panel rounded-xl flex-[1.5] relative overflow-hidden group">
            <div className="absolute inset-0 heatmap-layer pointer-events-none opacity-30 z-0" />
            <div className="absolute top-6 left-6 z-10">
              <h2 className="font-display text-xl text-primary-fixed-dim tracking-tight">
                {activeSourceId ? `节点 ${activeSourceId.slice(0, 8)}` : "监控画面"}
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <div className={`w-2 h-2 rounded-full ${connected ? "bg-primary-container pulse-indicator" : "bg-error opacity-40"}`} />
                <span className="text-[10px] text-on-surface-variant uppercase">
                  {connected ? "实时流：激活" : "空闲"}
                </span>
              </div>
            </div>

            {/* Toolbar buttons */}
            <div className="absolute top-6 right-6 z-10 flex gap-2">
              <button onClick={handleFenceSave} disabled={!fenceEditing}
                className="w-10 h-10 flex items-center justify-center bg-surface-container/60 border border-outline-variant/30 rounded-lg hover:bg-primary/20 transition-colors disabled:opacity-30"
                title="保存围栏">
                <span className="material-symbols-outlined text-[20px]">check</span>
              </button>
              <button onClick={() => setFenceEditing((v) => !v)}
                className={`w-10 h-10 flex items-center justify-center border rounded-lg transition-colors ${
                  fenceEditing ? "bg-primary-container/20 border-primary-container" : "bg-surface-container/60 border-outline-variant/30 hover:bg-primary/20"
                }`}
                title="绘制围栏">
                <span className="material-symbols-outlined text-[20px]">edit</span>
              </button>
              <button onClick={handleFenceClear} disabled={!hasFence}
                className="w-10 h-10 flex items-center justify-center bg-surface-container/60 border border-outline-variant/30 rounded-lg hover:bg-error/20 transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
                title="清除围栏">
                <span className="material-symbols-outlined text-[20px]">delete</span>
              </button>
            </div>

            {/* Video content */}
            <div className="w-full h-full flex items-center justify-center">
              <div style={{ position: "relative", display: "inline-block", maxWidth: "100%", maxHeight: "100%" }}>
                <VideoPanel
                  ref={videoPanelRef}
                  streaming={streaming}
                  previewImage={previewImage}
                  imageSrc={imageSrc}
                  width={videoSize.width}
                  height={videoSize.height}
                  detections={lastMessage?.detections || []}
                  tracks={lastMessage?.tracks || []}
                  fencePoints={fencePoints}
                />
                <FenceCanvas
                  width={videoSize.width}
                  height={videoSize.height}
                  points={fencePoints}
                  onPointsChange={setFencePoints}
                  editing={fenceEditing}
                />
              </div>
              {loading && !imageSrc && (
                <div className="absolute inset-0 flex flex-col items-center justify-center z-20 bg-background/60 backdrop-blur-sm">
                  <div className="w-16 h-16 border-4 border-primary-container/30 border-t-primary-container rounded-full animate-spin mb-4" />
                  <span className="text-sm text-primary-fixed-dim font-medium">模型加载中...</span>
                  <span className="text-[10px] text-on-surface-variant mt-1">正在初始化 YOLO 推理引擎</span>
                </div>
              )}
              {!streaming && !previewImage && (
                <div className="absolute inset-0 flex flex-col items-center justify-center opacity-50 pointer-events-none z-0">
                  <span className="material-symbols-outlined text-[120px] text-primary/10">videocam_off</span>
                  <span className="text-on-surface-variant text-sm mt-4">选择视频源开始监控</span>
                </div>
              )}
            </div>

            {/* Bottom bar */}
            <div className="absolute bottom-4 left-4 right-4 flex justify-between items-end pointer-events-none z-10">
              <div className="glass-panel px-3 py-1.5 rounded-lg border border-primary/20 text-[10px]">
                <span className="text-on-surface-variant">在线源:</span>
                <span className="text-primary-fixed-dim font-bold ml-1 text-glow">{onlineCount}</span>
              </div>
              <div className="glass-panel px-3 py-1.5 rounded-lg border border-error/20 text-[10px]">
                <span className="text-on-surface-variant">今日告警:</span>
                <span className="text-error font-bold ml-1">{alerts.length}</span>
              </div>
            </div>
          </div>
{alerts.length > 0 && (
            <div className="h-10 glass-panel rounded-xl overflow-hidden flex items-center px-4 relative flex-shrink-0">
              <div className="absolute left-0 top-0 bottom-0 px-3 bg-error/20 flex items-center z-10 border-r border-error/30">
                <span className="text-[10px] font-bold text-error uppercase">实时告警</span>
              </div>
              <div className="flex-1 whitespace-nowrap overflow-hidden">
                <div className="inline-block animate-marquee pl-[100%]">
                  {alerts.slice(-5).reverse().map((a, i) => (
                    <span key={i} className="mx-8 text-xs text-on-surface-variant flex items-center gap-2 inline-flex">
                      <span className="w-1.5 h-1.5 bg-error rounded-full" />
                      [{new Date().toLocaleTimeString()}] {a.class_name} #{a.track_id} 闯入围栏
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
          {/* Charts below video */}
          <div className="grid grid-cols-2 gap-3 flex-shrink-0" style={{ height: 180 }}>
            <div className="glass-panel rounded-xl p-3 flex flex-col">
              <h3 className="text-[10px] text-on-surface-variant uppercase tracking-wider mb-1">告警趋势 (7d)</h3>
              <div className="flex-1">
                <ReactECharts option={{
                  backgroundColor: "transparent",
                  tooltip: { trigger: "axis", textStyle: { fontSize: 10 } },
                  xAxis: { type: "category", data: chartDaily.map(d => d.date.slice(5)), axisLabel: { color: "#849495", fontSize: 9 }, axisLine: { lineStyle: { color: "#3a494b" } } },
                  yAxis: { type: "value", axisLabel: { color: "#849495", fontSize: 9 }, splitLine: { lineStyle: { color: "#2e3445" } } },
                  series: [{ data: chartDaily.map(d => d.count), type: "line", smooth: true, areaStyle: { color: "rgba(0,219,231,0.12)" }, lineStyle: { color: "#00dbe7", width: 1.5 }, itemStyle: { color: "#00dbe7" }, symbol: "none" }],
                  grid: { left: 30, right: 10, top: 5, bottom: 20 },
                }} style={{ height: "100%" }} />
              </div>
            </div>
            <div className="glass-panel rounded-xl p-3 flex flex-col">
              <h3 className="text-[10px] text-on-surface-variant uppercase tracking-wider mb-1">实时检测分布</h3>
              <div className="flex-1">
                <ReactECharts option={{
                  backgroundColor: "transparent",
                  tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)", textStyle: { fontSize: 10 } },
                  series: [{
                    type: "pie", radius: ["40%", "70%"], center: ["50%", "55%"],
                    data: liveClasses,
                    label: { color: "#b9cacb", fontSize: 9 },
                  }],
                }} style={{ height: "100%" }} />
              </div>
            </div>
          </div>

        </section>

        {/* RIGHT SIDEBAR - Stats */}
        <aside className="w-72 flex flex-col gap-3 p-3 border-l border-outline-variant/20 bg-surface-container-low/40 backdrop-blur-2xl overflow-y-auto custom-scrollbar">
          {/* KPI Cards */}
          <div className="grid grid-cols-2 gap-2">
            <div className="glass-panel p-3 rounded-lg flex flex-col gap-1 border-l-2 border-error">
              <p className="text-on-surface-variant text-[10px] uppercase">今日告警</p>
              <p className="text-xl text-error font-bold">{alerts.length}</p>
            </div>
            <div className="glass-panel p-3 rounded-lg flex flex-col gap-1 border-l-2 border-primary-container">
              <p className="text-on-surface-variant text-[10px] uppercase">在线源</p>
              <p className="text-xl text-primary-fixed-dim font-bold">{onlineCount}</p>
            </div>
            <div className="glass-panel p-3 rounded-lg flex flex-col gap-1 border-l-2 border-secondary">
              <p className="text-on-surface-variant text-[10px] uppercase">活跃跟踪</p>
              <p className="text-xl text-secondary font-bold">{lastMessage?.tracks?.length || 0}</p>
            </div>
            <div className="glass-panel p-3 rounded-lg flex flex-col gap-1 border-l-2 border-tertiary-fixed-dim">
              <p className="text-on-surface-variant text-[10px] uppercase">状态</p>
              <p className="text-xl text-tertiary-fixed-dim font-bold">{connected ? "在线" : "离线"}</p>
            </div>
          </div>

          {/* Status badges */}
          <div className="glass-panel p-3 rounded-lg flex flex-wrap gap-2">
            {connected && <span className="px-2 py-0.5 text-[10px] bg-primary-container/10 border border-primary-container/30 rounded-full text-primary-container">LIVE</span>}
            {orbActive && <span className="px-2 py-0.5 text-[10px] bg-secondary/10 border border-secondary/30 rounded-full text-secondary">ORB</span>}

          </div>

          {/* Recent alerts */}
          <div className="glass-panel p-3 rounded-lg flex-1 flex flex-col min-h-[200px]">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs text-on-surface-variant uppercase tracking-widest">近期告警</h2>
              <span className="text-[10px] text-primary-fixed-dim hover:underline cursor-pointer" onClick={() => setSourceTab("history")}>完整列表</span>
            </div>
            <div className="space-y-2 flex-1 overflow-y-auto custom-scrollbar">
              {recentHistory.map((r) => (
                <div key={r.id} className="p-2 bg-error-container/10 border-l-2 border-error rounded-r flex gap-2">
                  <span className="material-symbols-outlined text-error text-[16px]">dangerous</span>
                  <div className="min-w-0">
                    <p className="text-xs text-on-error-container font-bold truncate">{r.class_name} - #{r.id}</p>
                    <p className="text-[9px] text-on-surface-variant mt-0.5">
                      {r.timestamp?.replace("T", " ").slice(0, 16)} · {r.status}
                    </p>
                  </div>
                </div>
              ))}
              {recentHistory.length === 0 && (
                <div className="text-center text-on-surface-variant text-[10px] py-4">暂无告警记录</div>
              )}
            </div>
          </div>
        </aside>
      </main>

      {/* ===== BOTTOM BROADCAST BAR ===== */}
      <div className="z-50 h-11 glass-panel border-t border-outline-variant/20 flex items-stretch overflow-hidden flex-shrink-0">
        {/* Status pill */}
        <div className="flex items-center gap-2 px-4 border-r border-outline-variant/20 flex-shrink-0">
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase ${
            connected ? 'bg-primary-container/15 text-primary-container border border-primary-container/30' : 'bg-error/10 text-error border border-error/30'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-primary-container pulse-indicator' : 'bg-error'}`} />
            {connected ? ' LIVE' : ' IDLE'}
          </div>
          <span className="text-[10px] text-on-surface-variant">src: {onlineCount}</span>
        </div>

        {/* Alert count badge */}
        <div className="flex items-center gap-1 px-3 border-r border-outline-variant/20 flex-shrink-0 bg-error/5">
          <span className="material-symbols-outlined text-error text-[16px]">warning</span>
          <span className="text-xs text-error font-bold">{alerts.length}</span>
          <span className="text-[9px] text-on-surface-variant uppercase">alerts</span>
        </div>

        {/* Scrolling alert ticker */}
        <div className="flex-1 overflow-hidden relative">
          <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-background/80 to-transparent z-10 pointer-events-none" />
          <div className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-background/80 to-transparent z-10 pointer-events-none" />
          <div className="flex items-center h-full whitespace-nowrap">
            <div className="inline-flex animate-marquee pl-[100%] gap-12">
              {alerts.length > 0 ? alerts.slice(-8).reverse().map((a: any, i: number) => (
                <span key={i} className="inline-flex items-center gap-2 text-xs">
                  <span className="w-1 h-1 rounded-full bg-error" />
                  <span className="text-error font-medium">{a.class_name}</span>
                  <span className="text-on-surface-variant">#{a.track_id}</span>
                  <span className="text-[10px] text-on-surface-variant/60">{new Date().toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit',second:'2-digit'})}</span>
                  <span className="text-[9px] text-on-surface-variant/40 border border-outline-variant/30 rounded px-1">{(a.confidence * 100).toFixed(0)}%</span>
                </span>
              )) : (
                <span className="inline-flex items-center gap-2 text-xs">
                  <span className="w-1 h-1 rounded-full bg-on-surface-variant/30" />
                  <span className="text-on-surface-variant/50">system running - no alerts</span>
                  <span className="text-[10px] text-on-surface-variant/30">{new Date().toLocaleTimeString('zh-CN')}</span>
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-4 px-4 border-l border-outline-variant/20 flex-shrink-0">
          <a className="text-[10px] text-on-surface-variant hover:text-primary transition-colors cursor-pointer" onClick={() => navigate("/dashboard")}>stats</a>
          <a className="text-[10px] text-on-surface-variant hover:text-primary transition-colors cursor-pointer" onClick={() => setConfigOpen(true)}>config</a>
          <span className="text-[9px] text-on-surface-variant/50">v3.0</span>
        </div>
      </div>

      {/* Dialogs */}
      <ConfigDialog open={configOpen} onClose={() => setConfigOpen(false)} />
    </div>
  );
};

export default App;
