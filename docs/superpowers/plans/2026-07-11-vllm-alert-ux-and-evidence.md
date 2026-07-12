# vLLM 告警同步与证据增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将完成后的 vLLM 结论实时同步到右侧告警，并通过目标裁剪与结构化风险输出提升模型判断质量。

**Architecture:** vLLM 客户端从三张全景和三张 bbox 裁剪构造多图请求，解析风险 JSON；流管理在入库后广播 `alert_ready`；前端以临时告警 ID 将“分析中”卡片替换为完整记录。

**Tech Stack:** Python 3.9、FastAPI、httpx、OpenCV、React、TypeScript。

## Global Constraints

- vLLM 调用失败不阻断原告警，风险字段保持空值。
- 高风险、需复核、低风险分别映射为 `high`、`review`、`low`。
- 中文改动使用 UTF-8，并用 `git diff --check` 验证。

---

### Task 1: 证据帧与结构化 vLLM 结果

**Files:**
- Modify: `backend/vllm_client.py`
- Modify: `backend/tests/test_vllm_client.py`

- [ ] 写失败测试：bbox 扩边裁剪、六图 payload、JSON 与非 JSON 结果解析。
- [ ] 运行 `pytest backend/tests/test_vllm_client.py -v`，确认新增符号缺失。
- [ ] 实现 `crop_alert_frames`、结构化提示词及 `analyze_frames` 字典返回值。
- [ ] 重跑测试确认通过。

### Task 2: 告警持久化与完成事件

**Files:**
- Modify: `backend/database.py`
- Modify: `backend/routes/alerts.py`
- Modify: `backend/stream_bridge.py`

- [ ] 写失败测试：完成告警消息包含 `type=alert_ready` 和风险字段。
- [ ] 扩展 SQLite 迁移、`Alert` 字段和 API 序列化。
- [ ] 在保存告警后广播完整 `alert_ready` 记录；即时 `frame` 告警携带临时 `alert_key`。
- [ ] 运行后端测试和 Python 编译。

### Task 3: 前端右侧同步与风险展示

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AlertList.tsx`
- Modify: `frontend/src/components/AlertHistory.tsx`

- [ ] 为帧告警和完成告警定义类型。
- [ ] 收到 `alert_ready` 时替换临时项、刷新右侧历史；即时项显示“分析中”。
- [ ] 显示高风险、需复核、低风险标签及视觉证据。
- [ ] 运行 `npm run lint` 和 `npm run build`，记录现有阻断错误。

### Task 4: 验证

- [ ] 运行 `pytest backend/tests -v` 和 `python -m py_compile`。
- [ ] 严格 UTF-8 解码所有中文改动文件。
- [ ] 运行 `git diff --check` 并审阅差异。
