"""Conservative trajectory-based behavior candidates for fence alerts."""
from typing import Sequence


def classify_behavior_candidate(history: Sequence[tuple[float, list[int], bool]]) -> str:
    """Classify a short tracked bbox history without claiming a final action."""
    if len(history) < 2:
        return "normal"

    first_time, first_box, first_inside = history[0]
    last_time, last_box, last_inside = history[-1]
    duration = last_time - first_time
    first_height = max(first_box[3] - first_box[1], 1)
    first_width = max(first_box[2] - first_box[0], 1)
    first_area = first_width * first_height
    last_area = max((last_box[2] - last_box[0]) * (last_box[3] - last_box[1]), 1)
    upward_motion = first_box[1] - last_box[1]
    center_motion = abs((last_box[0] + last_box[2]) - (first_box[0] + first_box[2])) / 2

    if upward_motion >= first_height * 0.35 and last_area >= first_area * 1.15:
        return "possible_climbing"
    if first_inside != last_inside and center_motion >= first_height * 0.3:
        return "possible_crossing"
    if duration >= 3.0 and center_motion <= first_width * 1.5:
        return "loitering_near_fence"
    return "normal"
