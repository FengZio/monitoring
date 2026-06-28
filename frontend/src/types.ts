export interface Detection {
  class_id: number;
  class_name: string;
  confidence: number;
  bbox: [number, number, number, number];
  track_id: number | null;
}
export interface TrackState {
  track_id: number;
  class_name: string;
  bbox: [number, number, number, number];
  inside_fence: boolean;
}
export interface AlertInfo {
  class_name: string;
  confidence: number;
  bbox: [number, number, number, number];
  track_id: number;
}
export interface SSEMessage {
  type: "frame";
  source_id: string;
  frame_index: number;
  width: number;
  height: number;
  detections: Detection[];
  tracks: TrackState[];
  alerts: AlertInfo[];
  orb_tracking: boolean;
  fence_pixels: [number, number][];
}
export interface WSMessage extends SSEMessage { image: string; }
export interface FenceData {
  source_id: string;
  points: [number, number][];
  enabled: boolean;
  mode: string;

}
export interface VideoItem { filename: string; size: number; }
export interface VideoSource {
  source_id: string;
  type: string;
  arg: string;
  ready: boolean;
  fps: number;
}
export interface AlertRecord {
  id: number;
  class_name: string;
  confidence: number;
  bbox: string;
  timestamp: string;
  video_source: string;
  snapshot_path: string;
  clip_path: string | null;
  handled: boolean;
  status: string;
  handler: string | null;
  opinion: string | null;
  handled_at: string | null;
}
export interface AlertListResponse {
  total: number;
  page: number;
  page_size: number;
  items: AlertRecord[];
}
export interface ConfigData {
  email_enabled: boolean;
  email_smtp_server: string;
  email_smtp_port: number;
  email_user: string;
  email_password: string;
  email_to: string;
  dingtalk_enabled: boolean;
  dingtalk_webhook: string;
  alert_classes: string[];
  picgo_key: string;
}
export interface StatsOverview {
  total_today: number;
  pending: number;
  handle_rate: number;
  online_sources: number;
}
export interface DailyStat { date: string; count: number; }
export interface HourlyStat { hour: number; count: number; }
export interface ClassDistItem { name: string; count: number; ratio: number; }
export interface HeatmapData { points: [number, number][]; total: number; }

export const ALL_CLASSES = ["person", "bicycle", "car", "motorcycle", "bus", "truck"];