"""OpenAI-compatible vLLM client for multi-frame alert analysis."""
import base64
import json
import logging
import time
from threading import Lock
from typing import Iterable, Sequence

import cv2
import httpx
import numpy as np

logger = logging.getLogger(__name__)

VLLM_COOLDOWN_SECONDS = 60.0
_vllm_cooldown_lock = Lock()
_last_vllm_request_time = 0.0

PROMPT = (
    "这是监控摄像头拍摄到的连续三张时序组合图。每张图左侧为全景，右侧为同一目标及周边"
    "围栏或设施的放大 ROI；三张图片按时间从早到晚排列。分析是否存在攀爬墙体、跨越围栏、拉拽、撞击、拆卸或"
    "破坏设施的行为。仅输出 JSON："
    '{"risk_level":"high|review|low","is_destructive":true|false,'
    '"evidence":"具体帧序号、姿态和与设施的交互","uncertainty":"画面限制"}。'
    "观察到翻越、跨越或持续破坏设施时为 high；关键动作或设施被遮挡、看不清时为 review；"
    "仅在明确可见正常通行且未与设施交互时为 low。不能因无法确定而输出 low。"
    "不要使用 Markdown 代码块；evidence 必须是简短字符串，不要使用数组或对象。"
)


def select_frames_by_timestamp(
    buffer: Iterable[tuple[float, np.ndarray]], targets: Sequence[float]
) -> list[np.ndarray]:
    """Return the buffered frame nearest to each target timestamp."""
    entries = list(buffer)
    if not entries:
        return []
    return [min(entries, key=lambda item: abs(item[0] - target))[1] for target in targets]


def _sdi(reference_box: Sequence[float], candidate_box: Sequence[float], frame: np.ndarray) -> float:
    """Compute normalized center displacement and area change for two boxes."""
    rx1, ry1, rx2, ry2 = reference_box
    cx1, cy1, cx2, cy2 = candidate_box
    reference_center = ((rx1 + rx2) / 2, (ry1 + ry2) / 2)
    candidate_center = ((cx1 + cx2) / 2, (cy1 + cy2) / 2)
    height, width = frame.shape[:2]
    diagonal = max((width ** 2 + height ** 2) ** 0.5, 1.0)
    distance = ((reference_center[0] - candidate_center[0]) ** 2 + (reference_center[1] - candidate_center[1]) ** 2) ** 0.5
    reference_area = max((rx2 - rx1) * (ry2 - ry1), 1.0)
    candidate_area = max((cx2 - cx1) * (cy2 - cy1), 1.0)
    return 0.6 * distance / diagonal + 0.4 * abs(reference_area - candidate_area) / max(reference_area, candidate_area)


def select_adaptive_frames(
    buffer: Iterable[tuple[float, np.ndarray, dict]],
    trigger_time: float,
    track_id: int,
    trigger_box: Sequence[float],
    initial_window_seconds: float = 6.0,
    maximum_window_seconds: float = 10.0,
    threshold: float = 0.03,
) -> tuple[list[np.ndarray], list[list[float]]]:
    """Select the most distinct valid track frames before and after an alert."""
    entries = list(buffer)
    if not entries:
        return [], []

    def candidates(before: bool, window: float):
        return [entry for entry in entries if (entry[0] <= trigger_time if before else entry[0] >= trigger_time)
                and abs(entry[0] - trigger_time) <= window and track_id in entry[2]]

    def best(before: bool, window: float):
        options = candidates(before, window)
        if not options:
            return None, 0.0
        return max(options, key=lambda entry: _sdi(trigger_box, entry[2][track_id], entry[1])), max(
            _sdi(trigger_box, entry[2][track_id], entry[1]) for entry in options
        )

    pre, pre_score = best(True, initial_window_seconds)
    post, post_score = best(False, initial_window_seconds)
    if pre_score < threshold or post_score < threshold:
        pre, _ = best(True, maximum_window_seconds)
        post, _ = best(False, maximum_window_seconds)

    trigger = min(entries, key=lambda entry: abs(entry[0] - trigger_time))
    selected = [pre or trigger, trigger, post or trigger]
    frames = [entry[1] for entry in selected]
    boxes = [list(entry[2].get(track_id, trigger_box)) for entry in selected]
    return frames, boxes


def _encode_frame(frame: np.ndarray) -> str:
    success, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        raise ValueError("Failed to encode frame as JPEG")
    return base64.b64encode(jpeg.tobytes()).decode("ascii")


def crop_alert_frames(
    frames: Sequence[np.ndarray], bbox: Sequence[float], padding: int = 32
) -> list[np.ndarray]:
    """Crop a padded alert target region from every frame when bbox is valid."""
    if len(bbox) != 4:
        return []
    x1, y1, x2, y2 = (int(value) for value in bbox)
    if x2 <= x1 or y2 <= y1:
        return []
    crops = []
    for frame in frames:
        height, width = frame.shape[:2]
        left, top = max(0, x1 - padding), max(0, y1 - padding)
        right, bottom = min(width, x2 + padding), min(height, y2 + padding)
        if right <= left or bottom <= top:
            return []
        crops.append(frame[top:bottom, left:right].copy())
    return crops


def compose_context_frames(
    panoramas: Sequence[np.ndarray], crops: Sequence[np.ndarray]
) -> list[np.ndarray]:
    """Create one panorama-plus-ROI image for each temporal sample."""
    if len(panoramas) != len(crops):
        raise ValueError("Panorama and ROI counts must match")
    composed = []
    for panorama, crop in zip(panoramas, crops):
        height = panorama.shape[0]
        scaled_width = max(1, round(crop.shape[1] * height / crop.shape[0]))
        resized_crop = cv2.resize(crop, (scaled_width, height), interpolation=cv2.INTER_LINEAR)
        composed.append(cv2.hconcat([panorama, resized_crop]))
    return composed


def annotate_panorama_frames(
    frames: Sequence[np.ndarray], boxes: Sequence[Sequence[float]], fence_points: Sequence[Sequence[int]], track_id: int
) -> list[np.ndarray]:
    """Draw a translucent fence and the triggering target on panorama frames."""
    annotated = []
    polygon = np.array(fence_points, dtype=np.int32) if len(fence_points) >= 3 else None
    for frame, box in zip(frames, boxes):
        canvas = frame.copy()
        if polygon is not None:
            overlay = canvas.copy()
            cv2.fillPoly(overlay, [polygon], (0, 0, 255))
            canvas = cv2.addWeighted(overlay, 0.18, canvas, 0.82, 0)
            cv2.polylines(canvas, [polygon], True, (0, 0, 255), 2)
        x1, y1, x2, y2 = (int(value) for value in box)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(canvas, "person #{}".format(track_id), (x1, max(16, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        annotated.append(canvas)
    return annotated


def build_multimodal_payload(model: str, frames: Sequence[np.ndarray], prompt: str = PROMPT) -> dict:
    """Build one OpenAI-compatible chat completion request with ordered images."""
    if len(frames) < 3:
        raise ValueError("At least three frames are required")
    content = [{"type": "text", "text": prompt}]
    content.extend(
        {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64," + _encode_frame(frame)},
        }
        for frame in frames
    )
    return {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1,
    }


def _parse_analysis(content: object) -> dict:
    if not isinstance(content, str) or not content.strip():
        return {"analysis": "", "risk_level": "", "is_destructive": None}
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
        risk_level = result.get("risk_level")
        if risk_level not in {"high", "review", "low"}:
            raise ValueError("Invalid risk level")
        evidence = result.get("evidence", "")
        uncertainty = result.get("uncertainty", "")
        if isinstance(evidence, list):
            evidence_lines = []
            for item in evidence:
                if not isinstance(item, dict):
                    continue
                frame = item.get("frame", "?")
                posture = item.get("posture", "未说明")
                interaction = item.get("interaction_with_facility", "未说明")
                evidence_lines.append("第{}帧：{}；与设施交互：{}".format(frame, posture, interaction))
            evidence = "\n".join(evidence_lines)
        if not isinstance(evidence, str):
            evidence = str(evidence) if evidence else ""
        if not isinstance(uncertainty, str):
            uncertainty = str(uncertainty) if uncertainty else ""
        parts = [evidence]
        if uncertainty:
            parts.append("不确定性：" + uncertainty)
        analysis = "\n".join(part for part in parts if part).strip()
        return {
            "analysis": analysis,
            "risk_level": risk_level,
            "is_destructive": result.get("is_destructive") is True,
        }
    except (ValueError, TypeError, json.JSONDecodeError):
        return {"analysis": text, "risk_level": "review", "is_destructive": None}


def analyze_frames(config, frames: Sequence[np.ndarray], behavior_candidate: str = "normal") -> dict:
    """Return structured model analysis, or empty fields when analysis is unavailable."""
    empty = {"analysis": "", "risk_level": "", "is_destructive": None}
    if not getattr(config, "vllm_enabled", False):
        logger.info("vLLM analysis skipped: disabled")
        return empty
    if len(frames) < 3:
        logger.warning("vLLM analysis skipped: expected at least 3 frames, got %d", len(frames))
        return empty

    base_url = (getattr(config, "vllm_base_url", "") or "").rstrip("/")
    model = getattr(config, "vllm_model", "") or "GLM-4V-Flash"
    if not base_url:
        logger.warning("vLLM analysis enabled but API base URL is empty")
        return empty

    global _last_vllm_request_time
    with _vllm_cooldown_lock:
        now = time.monotonic()
        remaining = VLLM_COOLDOWN_SECONDS - (now - _last_vllm_request_time)
        if remaining > 0:
            logger.info("vLLM analysis skipped: global cooldown remaining=%.1fs", remaining)
            return {
                "analysis": "因全局 60 秒调用冷却，未进行视觉分析",
                "risk_level": "",
                "is_destructive": None,
            }
        _last_vllm_request_time = now

    headers = {"Content-Type": "application/json"}
    api_key = getattr(config, "vllm_api_key", "") or ""
    if api_key:
        headers["Authorization"] = "Bearer " + api_key

    try:
        context = (
            "\n场景：街头公共区域监控。红色半透明区域为电子围栏，绿色框为触发人物。"
            "轨迹规则候选为 {}，它仅用于提示复核，不得替代图像证据。".format(behavior_candidate)
        )
        payload = build_multimodal_payload(model, frames, PROMPT + context)
        timeout = max(1, int(getattr(config, "vllm_timeout_seconds", 30) or 30))
        endpoint = base_url + "/chat/completions"
        started_at = time.monotonic()
        logger.info("vLLM request started: model=%s frames=%d endpoint=%s", model, len(frames), endpoint)
        response = httpx.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=timeout,
            trust_env=False,
        )
        elapsed_ms = (time.monotonic() - started_at) * 1000
        logger.info("vLLM response received: status=%d elapsed_ms=%.0f", response.status_code, elapsed_ms)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        result = _parse_analysis(content)
        logger.info("vLLM analysis completed: risk_level=%s destructive=%s", result["risk_level"], result["is_destructive"])
        return result
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500].replace("\n", " ")
        logger.warning("vLLM request rejected: status=%d body=%s", exc.response.status_code, body)
        return empty
    except Exception as exc:
        logger.warning("vLLM multi-frame analysis failed: %s", exc)
        return empty
