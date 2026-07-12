from collections import deque

import numpy as np
import pytest

import vllm_client
from vllm_client import (
    analyze_frames,
    build_multimodal_payload,
    crop_alert_frames,
    compose_context_frames,
    annotate_panorama_frames,
    select_adaptive_frames,
    select_frames_by_timestamp,
)


@pytest.fixture(autouse=True)
def reset_vllm_cooldown(monkeypatch):
    monkeypatch.setattr(vllm_client, "_last_vllm_request_time", 0.0)


def test_select_frames_uses_nearest_frame_and_duplicates_when_needed():
    frame_a = np.zeros((2, 2, 3), dtype=np.uint8)
    frame_b = np.ones((2, 2, 3), dtype=np.uint8)
    frames = deque([(0.0, frame_a), (2.0, frame_b)])

    selected = select_frames_by_timestamp(frames, [-2.0, 0.0, 2.0])

    assert selected[0] is frame_a
    assert selected[1] is frame_a
    assert selected[2] is frame_b


def test_payload_contains_prompt_and_three_data_url_images():
    frames = [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(3)]

    payload = build_multimodal_payload("GLM-4V-Flash", frames)

    content = payload["messages"][0]["content"]
    assert payload["model"] == "GLM-4V-Flash"
    assert content[0]["type"] == "text"
    assert len(content) == 4
    assert all(item["image_url"]["url"].startswith("data:image/jpeg;base64,") for item in content[1:])


def test_analyze_frames_returns_empty_when_disabled():
    config = type("Config", (), {"vllm_enabled": False})()
    frames = [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(3)]

    assert analyze_frames(config, frames) == {
        "analysis": "", "risk_level": "", "is_destructive": None,
    }


def test_analyze_frames_returns_completion_text(monkeypatch):
    request = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": " 存在攀爬风险 "}}]}

    def post(*args, **kwargs):
        request["url"] = args[0]
        request.update(kwargs)
        return Response()

    monkeypatch.setattr(vllm_client.httpx, "post", post)
    config = type("Config", (), {
        "vllm_enabled": True, "vllm_base_url": "http://vllm/v1",
        "vllm_model": "GLM-4V-Flash", "vllm_api_key": "key",
        "vllm_timeout_seconds": 30,
    })()
    frames = [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(3)]

    assert analyze_frames(config, frames) == {
        "analysis": "存在攀爬风险", "risk_level": "review", "is_destructive": None,
    }
    assert request["url"] == "http://vllm/v1/chat/completions"
    assert request["headers"]["Authorization"] == "Bearer key"
    assert request["json"]["model"] == "GLM-4V-Flash"


def test_crop_alert_frames_adds_padding_and_keeps_frame_bounds():
    frame = np.zeros((100, 120, 3), dtype=np.uint8)

    crops = crop_alert_frames([frame], [10, 20, 30, 40], padding=10)

    assert len(crops) == 1
    assert crops[0].shape == (40, 40, 3)


def test_payload_accepts_panorama_and_cropped_frames():
    frames = [np.zeros((4, 4, 3), dtype=np.uint8) for _ in range(6)]

    payload = build_multimodal_payload("GLM-4V-Flash", frames)

    assert len(payload["messages"][0]["content"]) == 7


def test_analyze_frames_parses_structured_risk_result(monkeypatch):
    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": (
                '{"risk_level":"high","is_destructive":true,'
                '"evidence":"第三帧跨越围栏","uncertainty":""}'
            )}}]}

    monkeypatch.setattr(vllm_client.httpx, "post", lambda *args, **kwargs: Response())
    config = type("Config", (), {
        "vllm_enabled": True, "vllm_base_url": "http://vllm/v1",
        "vllm_model": "GLM-4V-Flash", "vllm_api_key": "",
        "vllm_timeout_seconds": 30,
    })()
    frames = [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(3)]

    assert analyze_frames(config, frames) == {
        "analysis": "第三帧跨越围栏", "risk_level": "high", "is_destructive": True,
    }


def test_analyze_frames_sends_six_panorama_and_cropped_frames(monkeypatch):
    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"risk_level":"review","is_destructive":false,"evidence":"遮挡","uncertainty":""}'}}]}

    called = []
    monkeypatch.setattr(vllm_client.httpx, "post", lambda *args, **kwargs: called.append(kwargs) or Response())
    config = type("Config", (), {
        "vllm_enabled": True, "vllm_base_url": "http://vllm/v1",
        "vllm_model": "glm-4.6v-flash", "vllm_api_key": "",
        "vllm_timeout_seconds": 30,
    })()
    frames = [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(6)]

    result = analyze_frames(config, frames)

    assert result["risk_level"] == "review"
    assert len(called) == 1
    assert len(called[0]["json"]["messages"][0]["content"]) == 7


def test_analyze_frames_enforces_global_sixty_second_cooldown(monkeypatch):
    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"risk_level":"low","is_destructive":false,"evidence":"正常通行","uncertainty":""}'}}]}

    monkeypatch.setattr(vllm_client.httpx, "post", lambda *args, **kwargs: Response())
    monkeypatch.setattr(vllm_client, "_last_vllm_request_time", 0.0)
    monkeypatch.setattr(vllm_client.time, "monotonic", lambda: 100.0)
    config = type("Config", (), {
        "vllm_enabled": True, "vllm_base_url": "http://vllm/v1",
        "vllm_model": "glm-4.6v-flash", "vllm_api_key": "",
        "vllm_timeout_seconds": 30,
    })()
    frames = [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(3)]

    assert analyze_frames(config, frames)["risk_level"] == "low"
    assert analyze_frames(config, frames) == {
        "analysis": "因全局 60 秒调用冷却，未进行视觉分析",
        "risk_level": "",
        "is_destructive": None,
    }


def test_select_adaptive_frames_uses_largest_pre_and_post_track_difference():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    buffer = [
        (0.0, frame, {7: [5, 10, 15, 30]}),
        (4.0, frame, {7: [20, 10, 30, 30]}),
        (6.0, frame, {7: [40, 10, 50, 30]}),
        (10.0, frame, {7: [70, 10, 80, 30]}),
        (16.0, frame, {7: [90, 10, 100, 30]}),
    ]

    frames, boxes = select_adaptive_frames(buffer, 10.0, 7, [70, 10, 80, 30])

    assert frames == [frame, frame, frame]
    assert boxes == [[20, 10, 30, 30], [70, 10, 80, 30], [90, 10, 100, 30]]


def test_compose_context_frames_combines_each_panorama_with_its_roi():
    panoramas = [np.zeros((40, 60, 3), dtype=np.uint8) for _ in range(3)]
    crops = [np.ones((20, 10, 3), dtype=np.uint8) for _ in range(3)]

    composed = compose_context_frames(panoramas, crops)

    assert len(composed) == 3
    assert composed[0].shape == (40, 80, 3)
    assert composed[0][0, -1, 0] == 1


def test_analyze_frames_formats_list_evidence_into_readable_text(monkeypatch):
    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            content = '{"risk_level":"review","is_destructive":false,"evidence":[{"frame":1,"posture":"normal walking","interaction_with_facility":"none"},{"frame":2,"posture":"bending down","interaction_with_facility":"none"}],"uncertainty":"posture unclear"}'
            return {"choices": [{"message": {"content": content}}]}

    monkeypatch.setattr(vllm_client.httpx, "post", lambda *args, **kwargs: Response())
    config = type("Config", (), {
        "vllm_enabled": True, "vllm_base_url": "http://vllm/v1",
        "vllm_model": "glm-4.6v-flash", "vllm_api_key": "",
        "vllm_timeout_seconds": 30,
    })()
    frames = [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(3)]

    result = analyze_frames(config, frames)

    assert result["risk_level"] == "review"
    assert result["analysis"] == "第1帧：normal walking；与设施交互：none\n第2帧：bending down；与设施交互：none\n不确定性：posture unclear"


def test_analyze_frames_strips_markdown_json_fence(monkeypatch):
    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            content = '```json\n{"risk_level":"review","is_destructive":false,"evidence":"未发现接触设施","uncertainty":"画面遮挡"}\n```'
            return {"choices": [{"message": {"content": content}}]}

    monkeypatch.setattr(vllm_client.httpx, "post", lambda *args, **kwargs: Response())
    config = type("Config", (), {
        "vllm_enabled": True, "vllm_base_url": "http://vllm/v1",
        "vllm_model": "glm-4.6v-flash", "vllm_api_key": "",
        "vllm_timeout_seconds": 30,
    })()
    frames = [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(3)]

    assert analyze_frames(config, frames)["analysis"] == "未发现接触设施\n不确定性：画面遮挡"


def test_annotate_panorama_frames_draws_fence_and_target_box():
    frame = np.zeros((40, 40, 3), dtype=np.uint8)

    annotated = annotate_panorama_frames([frame], [[10, 10, 20, 25]], [(2, 2), (35, 2), (35, 35)], 9)

    assert annotated[0].shape == frame.shape
    assert np.any(annotated[0] != frame)
