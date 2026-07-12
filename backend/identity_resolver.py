"""Map short-lived tracker IDs to stable logical identities per video source."""
import time


class IdentityResolver:
    def __init__(self, max_gap_seconds: float = 5.0):
        self.max_gap_seconds = max_gap_seconds
        self._next_id = 1
        self._active = {}
        self._lost = {}

    @staticmethod
    def _iou(a, b):
        x1, y1 = max(a[0], b[0]), max(a[1], b[1])
        x2, y2 = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        union = max(1, (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter)
        return inter / union

    def resolve(self, raw_id, bbox, now=None):
        now = time.monotonic() if now is None else now
        if raw_id in self._active:
            logical_id, _, _ = self._active[raw_id]
            self._active[raw_id] = (logical_id, now, bbox)
            return logical_id
        candidates = [(self._iou(bbox, old_bbox), logical_id) for logical_id, (seen, old_bbox) in self._lost.items() if now - seen <= self.max_gap_seconds]
        score, logical_id = max(candidates) if candidates else (0, self._next_id)
        if score < 0.3:
            logical_id = self._next_id
            self._next_id += 1
        self._active[raw_id] = (logical_id, now, bbox)
        return logical_id

    def retire_missing(self, seen_raw_ids, now=None):
        now = time.monotonic() if now is None else now
        for raw_id in list(self._active):
            if raw_id not in seen_raw_ids:
                logical_id, _, bbox = self._active.pop(raw_id)
                self._lost[logical_id] = (now, bbox)
        self._lost = {key: value for key, value in self._lost.items() if now - value[0] <= self.max_gap_seconds}
