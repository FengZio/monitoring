# 告警详情与中央录像播放 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让右侧告警完整可读，并在主画面中央播放历史录像。

**Architecture:** 右侧展开状态保存在 `App`；历史组件通过回调把录像 URL 向上交给 `App`，中央区域按 URL 条件渲染覆盖式播放器。

### Task 1: 历史录像播放回调

- [ ] 给 `AlertHistory` 增加 `onPlayClip?: (url: string) => void`，写入历史表播放按钮失败测试或 TypeScript 类型检查。
- [ ] 将内部录像弹窗改为调用回调，回调缺失时保留本地播放。

### Task 2: 右侧详情与中央播放器

- [ ] 在 `App` 增加展开告警 ID 与中央录像 URL 状态。
- [ ] 右侧卡片点击后显示完整详情，使用展开/收起图标。
- [ ] 将 `AlertHistory` 回调传入左侧历史视图，中央视频容器渲染关闭按钮和播放器。

### Task 3: 验证

- [ ] 运行 `npm run lint`、`npm run build` 并区分既有错误。
- [ ] 严格 UTF-8 和 `git diff --check`。
