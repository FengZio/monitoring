# 电子围栏监控系统 (E-Fence Monitor v3.0)

基于 YOLOv8 + ByteTrack 的实时视频监控与电子围栏预警系统。

## 技术栈

**后端**
- FastAPI (Python)
- YOLOv8 / YOLO26 目标检测
- ByteTrack 多目标追踪
- MediaMTX 流媒体服务 (RTSP/RTMP/WebRTC/HLS)
- SQLite 数据库
- SSE / WebSocket 实时推送
- 邮件 & 钉钉通知

**前端**
- React 19 + TypeScript + Vite
- Ant Design 6.x
- ECharts 数据可视化
- zrender Canvas 围栏绘制
- Tailwind CSS

## 快速开始

### 1. 获取模型文件

从 [Ultralytics](https://docs.ultralytics.com/) 下载 YOLO 模型放置到 `backend/models/` 目录:

```
backend/models/
├── yolov8n.pt
└── yolo26n.pt  (可选)
```

### 2. 获取 MediaMTX

从 [MediaMTX Releases](https://github.com/bluenviron/mediamtx/releases) 下载 Windows 版，将 `mediamtx.exe` 放入 `backend/bin/`。

### 3. 后端启动

```bash
cd backend
pip install -r requirements.txt
python main.py
```

服务运行在 `http://localhost:8000`

### 4. 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端运行在 `http://localhost:5173`

## 功能特性

- **多源视频流接入**: 支持 RTSP/RTMP/本地文件多种输入
- **实时目标检测**: YOLO 检测人员、车辆等目标
- **电子围栏**: 自定义多边形围栏，越界/闯入检测
- **多目标追踪**: ByteTrack 跨帧追踪，减少重复告警
- **标定功能**: 像素坐标 <-> 世界坐标转换
- **告警管理**: 截图、录像片段、处理状态跟踪
- **通知推送**: 邮件 + 钉钉机器人
- **实时看板**: ECharts 统计图表 + SSE 实时更新

## 项目结构

```
monitoring/
├── backend/              # FastAPI 后端
│   ├── main.py           # 入口
│   ├── config.py         # 配置
│   ├── database.py       # 数据库模型
│   ├── detector.py       # YOLO 检测器
│   ├── fence_checker.py  # 围栏检测
│   ├── notifier.py       # 通知服务
│   ├── stream_bridge.py  # 流管理
│   ├── media_server.py   # MediaMTX 管理
│   ├── sse_manager.py    # SSE 管理
│   ├── bin/              # MediaMTX 可执行文件
│   ├── models/           # YOLO 模型
│   └── routes/           # API 路由
├── frontend/             # React 前端
│   └── src/
│       ├── components/   # 组件
│       ├── hooks/        # 自定义 Hooks
│       └── services/     # API 服务
└── hls/                  # HLS 分片 (运行时生成)
```