# BoT-SORT ReID 与逻辑身份 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用每视频源隔离的 BoT-SORT + ReID 和稳定 `logical_id` 降低人员转身、短遮挡导致的 ID 切换。

**Architecture:** YOLO 检测权重维持共享；每个 `source_id` 创建独立 BoT-SORT 实例。追踪器 raw ID 经过 `IdentityResolver` 续接为 `logical_id`，围栏、Pose、轨迹和行为规则只使用逻辑身份。

**Tech Stack:** Python 3.9、Ultralytics 8.3、BoT-SORT、ReID、OpenCV、NumPy。

## Global Constraints

- 禁止共享 `model.track(persist=True)` 的 tracker 状态。
- ReID 模型加载失败时回退到每源 BoT-SORT 无外观特征模式。
- 围栏、姿态与告警不得因 ReID 失败中断。
- 每源 ReID 频率限制为每 5 帧一次，适配 RTX 3050 4GB。

---

### Task 1: 依赖与 BoT-SORT 配置

**Files:**
- Create: `backend/botsort_reid.yaml`
- Create: `backend/tests/test_tracker_config.py`

- [ ] 写失败测试，断言配置启用 `tracker_type=botsort`、`with_reid=true`、`track_buffer=90`。
- [ ] 在启动服务的 Python 环境运行 `python -c "import torch, torchvision, ultralytics"`。
- [ ] 创建配置：`track_high_thresh: 0.25`、`track_low_thresh: 0.1`、`new_track_thresh: 0.25`、`match_thresh: 0.8`、`proximity_thresh: 0.5`、`appearance_thresh: 0.8`、`with_reid: true`、`model: auto`。
- [ ] 运行 `pytest backend/tests/test_tracker_config.py -v`。

### Task 2: 每源追踪器

**Files:**
- Create: `backend/source_tracker.py`
- Modify: `backend/detector.py`
- Modify: `backend/stream_bridge.py`
- Test: `backend/tests/test_source_tracker.py`

- [ ] 写失败测试，创建两个 source tracker 并断言其 raw tracker 状态对象不相同。
- [ ] 将 `Detector.detect` 改为仅返回检测框；`SourceTracker.update(detections, frame)` 返回附带 raw ID 的检测结果。
- [ ] 在 `StreamManager.add_source` 创建 `SourceTracker(source_id)`，传入对应 worker。
- [ ] 运行 source tracker 测试与单源视频回放。

### Task 3: logical_id 续接

**Files:**
- Create: `backend/identity_resolver.py`
- Modify: `backend/source_tracker.py`
- Test: `backend/tests/test_identity_resolver.py`

- [ ] 写失败测试：旧 raw ID 在 5 秒内消失，新 raw ID 以高 IoU、近中心距离和相似 HSV 外观出现时复用同一 `logical_id`。
- [ ] 实现候选门控：时间 <= 5 秒、IoU >= 0.3 或归一化中心距离 <= 0.08；匹配代价为 IoU、中心距离和外观距离加权和。
- [ ] 未通过门控时分配新 `logical_id`；过期身份状态在 10 秒后删除。
- [ ] 运行 identity resolver 测试。

### Task 4: 状态迁移与验收

**Files:**
- Modify: `backend/fence_checker.py`
- Modify: `backend/pose_detector.py`
- Modify: `backend/stream_bridge.py`
- Test: `backend/tests/test_fence_checker.py`

- [ ] 写失败测试：同一 logical ID 的 raw ID 切换后，围栏状态、轨迹和 Pose 历史长度连续。
- [ ] 将 `FenceChecker`、Pose map、环形缓冲 track 元数据和告警 `track_id` 改为使用 `logical_id`；raw ID 仅用于调试日志。
- [ ] 添加限频 INFO 日志：每源 raw ID、logical ID、ReID 匹配/新建数量。
- [ ] 运行 `pytest backend/tests -v`、单源遮挡回放与双源并行回放；验收标准是人物短暂遮挡后 logical ID 不变化，且两源 ID 状态互不影响。
