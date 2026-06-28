import React, { useState, useEffect } from "react";
import { Button, Upload, Tag, Space, Select, message } from "antd";
import {
  PlayCircleOutlined, PauseCircleOutlined, SettingOutlined, EditOutlined,
  CheckOutlined, DeleteOutlined, UploadOutlined, CameraOutlined,
  CaretRightOutlined, DashboardOutlined, PlusOutlined,
} from "@ant-design/icons";
import { uploadVideo, listVideos, previewWebcam, previewFile } from "../services/api";
import type { VideoItem } from "../types";

interface ToolbarProps {
  streaming: boolean;
  fenceEditing: boolean;
  hasFence: boolean;
  connected: boolean;
  orbActive: boolean;
  activeSourceId: string;
  onConnect: (sourceId: string) => void;
  onDisconnect: () => void;
  onFenceEditToggle: () => void;
  onFenceClear: () => void;
  onFenceSave: () => void;
  onConfigOpen: () => void;
  onAddWebcam: () => void;
  onAddFile: (filename: string) => void;
  onRemoveSource: () => void;
  onPreview?: (b64: string) => void;
  onOpenDashboard: () => void;
}

const Toolbar: React.FC<ToolbarProps> = ({
  streaming, fenceEditing, hasFence, connected,
  orbActive, activeSourceId, onConnect, onDisconnect,
  onFenceEditToggle, onFenceClear, onFenceSave, onConfigOpen,
  onAddWebcam, onAddFile,
  onRemoveSource, onPreview, onOpenDashboard,
}) => {
  const [videoFiles, setVideoFiles] = useState<VideoItem[]>([]);

  useEffect(() => {
    listVideos().then((d) => setVideoFiles(d.videos || [])).catch(() => {});
  }, []);

  const handleUpload = async (file: File) => {
    try {
      const res = await uploadVideo(file);
      setVideoFiles((prev) => [{ filename: res.filename, size: 0 }, ...prev]);
      message.success("uploaded");
      try {
        const data = await previewFile(res.filename);
        if (data.frame) onPreview?.(data.frame);
      } catch { /* ok */ }
    } catch { message.error("upload failed"); }
    return false;
  };

  const handleWebcamPreview = async () => {
    try {
      const data = await previewWebcam(0);
      if (data.frame) onPreview?.(data.frame);
      message.success("preview ready - click start webcam to begin");
    } catch { message.error("webcam not available"); }
  };

  const handleFilePreview = async (filename: string) => {
    try {
      const data = await previewFile(filename);
      if (data.frame) onPreview?.(data.frame);
    } catch { /* ok */ }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 20px",
      background: "linear-gradient(135deg, #0d1b2a 0%, #1b2838 100%)",
      borderBottom: "1px solid rgba(255,255,255,0.08)", flexWrap: "wrap", minHeight: 56 }}>
      <span style={{ color: "#e0e0e0", fontWeight: 700, fontSize: 16, marginRight: 8 }}>Monitor v3</span>
      <Tag color={connected ? (streaming ? "success" : "processing") : "error"}>
        {connected ? (streaming ? "LIVE" : "connected") : "offline"}
      </Tag>
      {activeSourceId && <Tag color="blue">{activeSourceId.slice(0,8)}</Tag>}
      {orbActive && <Tag color="purple">ORB</Tag>}

      <div style={{ width: 1, height: 28, background: "rgba(255,255,255,0.15)", margin: "0 4px" }} />

      <Space size={4}>
        <Button icon={<CameraOutlined />} size="middle" style={{ borderColor: "#52c41a", color: "#52c41a" }}
          onClick={() => { handleWebcamPreview(); }}>webcam</Button>
        <Button icon={<PlusOutlined />} size="middle" type="primary" onClick={onAddWebcam}>
          start webcam
        </Button>
        <Upload accept="video/*" showUploadList={false} beforeUpload={handleUpload}>
          <Button icon={<UploadOutlined />} size="middle" style={{ borderColor: "#1677ff", color: "#1677ff" }}>upload</Button>
        </Upload>
        <Select placeholder="play file" size="middle" style={{ minWidth: 140 }}
          value={undefined}
          onChange={(filename) => { handleFilePreview(filename); onAddFile(filename); }}
          options={videoFiles.map((f) => ({ label: f.filename, value: f.filename }))} />
      </Space>

      <div style={{ width: 1, height: 28, background: "rgba(255,255,255,0.15)", margin: "0 4px" }} />

      {streaming ? (
        <Button icon={<PauseCircleOutlined />} size="middle" danger type="primary" onClick={onDisconnect}>stop</Button>
      ) : null}
      {activeSourceId && <Button icon={<DeleteOutlined />} size="middle" danger onClick={onRemoveSource}>remove</Button>}

      <div style={{ flex: 1 }} />

      <Space size={4}>
        {fenceEditing ? (
          <Button icon={<CheckOutlined />} size="middle" type="primary"
            style={{ background: "#52c41a", borderColor: "#52c41a" }} onClick={onFenceSave}>save</Button>
        ) : (
          <Button icon={<EditOutlined />} size="middle" onClick={onFenceEditToggle}
            style={{ borderColor: "#fa8c16", color: "#fa8c16" }}>draw</Button>
        )}
        {hasFence && <Button icon={<DeleteOutlined />} size="middle" danger onClick={onFenceClear}>clear</Button>}
      </Space>

      <div style={{ width: 1, height: 28, background: "rgba(255,255,255,0.15)", margin: "0 4px" }} />

      <Button icon={<DashboardOutlined />} size="middle" onClick={onOpenDashboard} style={{ borderColor: "#722ed1", color: "#722ed1" }}>dashboard</Button>
      <Button icon={<SettingOutlined />} size="middle" onClick={onConfigOpen}>settings</Button>
    </div>
  );
};

export default Toolbar;