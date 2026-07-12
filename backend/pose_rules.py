"""Conservative pose-keypoint behavior candidates."""
from typing import Sequence


def _midpoint(points: dict, left: int, right: int):
    if left not in points or right not in points:
        return None
    if points[left][2] < 0.4 or points[right][2] < 0.4:
        return None
    return ((points[left][0] + points[right][0]) / 2, (points[left][1] + points[right][1]) / 2)


def classify_pose_candidate(history: Sequence[dict]) -> str:
    """Return a pose candidate only when tilt and upward movement agree."""
    if len(history) < 2:
        return "normal"
    first, last = history[0], history[-1]
    shoulders = _midpoint(last, 5, 6)
    hips = _midpoint(last, 11, 12)
    first_ankles = _midpoint(first, 15, 16)
    last_ankles = _midpoint(last, 15, 16)
    if not all([shoulders, hips, first_ankles, last_ankles]):
        return "normal"
    torso_height = abs(hips[1] - shoulders[1])
    if torso_height < 1:
        return "normal"
    torso_tilt = abs(hips[0] - shoulders[0]) / torso_height
    ankle_rise = first_ankles[1] - last_ankles[1]
    if torso_tilt >= 0.30 and ankle_rise >= torso_height * 0.20:
        return "possible_climbing_pose"
    return "normal"
