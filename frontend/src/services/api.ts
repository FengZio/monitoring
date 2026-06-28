import type { FenceData, VideoItem, VideoSource, AlertListResponse, ConfigData, StatsOverview, DailyStat, HourlyStat, ClassDistItem, HeatmapData } from "../types";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  if (!resp.ok) { const err = await resp.text(); throw new Error(err); }
  return resp.json();
}

// ---- Video ----
export async function uploadVideo(file: File): Promise<{ filename: string }> {
  const form = new FormData(); form.append("file", file);
  const resp = await fetch("/api/video/upload", { method: "POST", body: form });
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}
export function addWebcamSource(cameraId = 0): Promise<{ source_id: string }> {
  return request("/api/video/sources/webcam", { method: "POST", body: JSON.stringify({ camera_id: cameraId }) });
}
export function addFileSource(filename: string): Promise<{ source_id: string }> {
  return request(`/api/video/sources/file/${filename}`, { method: "POST" });
}
export function removeSource(sourceId: string) {
  return request(`/api/video/sources/${sourceId}`, { method: "DELETE" });
}
export function listSources(): Promise<{ sources: VideoSource[] }> {
  return request("/api/video/sources");
}
export function listVideos(): Promise<{ videos: VideoItem[] }> {
  return request("/api/video/list");
}
export function previewWebcam(cameraId = 0): Promise<{ frame: string; width: number; height: number }> {
  return request(`/api/video/preview/webcam?camera_id=${cameraId}`, { method: "POST" });
}
export function previewFile(filename: string): Promise<{ frame: string; width: number; height: number }> {
  return request(`/api/video/preview/file/${filename}`, { method: "POST" });
}

// ---- Fence ----
export function getFence(sourceId = "default"): Promise<FenceData> {
  return request(`/api/fence?source_id=${sourceId}`);
}
export function saveFence(points: [number, number][], sourceId = "default", mode = "restricted") {
  return request(`/api/fence?source_id=${sourceId}`, { method: "POST", body: JSON.stringify({ points, mode }) });
}
export function clearFence(sourceId = "default") {
  return request(`/api/fence?source_id=${sourceId}`, { method: "DELETE" });
}
export function saveCalibration(pixelPoints: [number, number][], worldPoints: [number, number][], sourceId = "default") {
  return request(`/api/fence/calibrate?source_id=${sourceId}`, { method: "POST", body: JSON.stringify({ pixel_points: pixelPoints, world_points: worldPoints }) });
}

// ---- Alerts ----
export function getAlerts(page = 1, pageSize = 20, status = "", sourceId = ""): Promise<AlertListResponse> {
  let url = `/api/alerts?page=${page}&page_size=${pageSize}`;
  if (status) url += `&status=${status}`;
  if (sourceId) url += `&source_id=${sourceId}`;
  return request(url);
}
export function updateAlertStatus(alertId: number, status: string, handler = "", opinion = "") {
  return request(`/api/alerts/${alertId}/status`, { method: "PATCH", body: JSON.stringify({ status, handler, opinion }) });
}
export function getAlertClipUrl(alertId: number): string {
  return `/api/alerts/${alertId}/clip`;
}

// ---- Stats ----
export function getStatsOverview(): Promise<StatsOverview> {
  return request("/api/stats/overview");
}
export function getStatsDaily(days = 7): Promise<{ daily: DailyStat[] }> {
  return request(`/api/stats/daily?days=${days}`);
}
export function getStatsHourly(date = ""): Promise<{ hourly: HourlyStat[] }> {
  let url = "/api/stats/hourly";
  if (date) url += `?date=${date}`;
  return request(url);
}
export function getClassDistribution(): Promise<{ distribution: ClassDistItem[] }> {
  return request("/api/stats/class_distribution");
}
export function getHeatmap(sourceId = ""): Promise<HeatmapData> {
  let url = "/api/stats/heatmap";
  if (sourceId) url += `?source_id=${sourceId}`;
  return request(url);
}

// ---- Config ----
export function getConfig(): Promise<ConfigData> { return request("/api/config"); }
export function saveConfig(data: ConfigData) { return request("/api/config", { method: "POST", body: JSON.stringify(data) }); }
export function checkHealth() { return request<{ status: string; streaming: boolean }>("/api/health"); }
