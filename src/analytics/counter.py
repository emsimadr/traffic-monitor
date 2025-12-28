from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from domain.models import CountEvent
from detection.tracker import TrackedVehicle


def _side_of_line(p: Tuple[float, float], a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """Signed area (cross product) to determine which side of a->b the point lies on."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _segments_intersect(p1: Tuple[float, float], p2: Tuple[float, float], a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    """Check if segment p1->p2 intersects with segment a->b (inclusive)."""
    def orient(x, y, z):
        return (y[0] - x[0]) * (z[1] - x[1]) - (y[1] - x[1]) * (z[0] - x[0])

    o1 = orient(p1, p2, a)
    o2 = orient(p1, p2, b)
    o3 = orient(a, b, p1)
    o4 = orient(a, b, p2)

    if (o1 == 0 and o2 == 0 and o3 == 0 and o4 == 0):
        return False  # colinear overlap not expected for our use; treat as no hard crossing

    return (o1 * o2 <= 0) and (o3 * o4 <= 0)


def _distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


@dataclass
class GateCounterConfig:
    line_a: List[Tuple[int, int]]
    line_b: List[Tuple[int, int]]
    direction_labels: Dict[str, str]
    max_gap_frames: int
    min_age_frames: int
    min_displacement_px: float


class GateCounter:
    """Two-line gate counting with A->B / B->A sequencing and constraints."""

    def __init__(self, cfg: GateCounterConfig):
        self.cfg = cfg
        self._state: Dict[int, Dict[str, Optional[int]]] = {}

    def process(self, tracks: List[TrackedVehicle], frame_idx: int) -> List[CountEvent]:
        events: List[CountEvent] = []
        line_a = self.cfg.line_a
        line_b = self.cfg.line_b
        if not line_a or not line_b or len(line_a) != 2 or len(line_b) != 2:
            return events

        for tv in tracks:
            if len(tv.trajectory) < 2:
                continue

            st = self._state.setdefault(
                tv.vehicle_id,
                {
                    "first_frame": frame_idx,
                    "first_pos": tv.trajectory[0],
                    "last_line": None,
                    "last_line_frame": None,
                    "line_a_frame": None,
                    "line_b_frame": None,
                    "counted": False,
                },
            )
            if st["counted"]:
                continue

            prev = tv.trajectory[-2]
            curr = tv.trajectory[-1]

            crossed_a = self._crossed_line(prev, curr, line_a)
            crossed_b = self._crossed_line(prev, curr, line_b)

            seq = None
            if crossed_a:
                if st["last_line"] == "B":
                    seq = "B_TO_A"
                    st["line_a_frame"] = frame_idx
                else:
                    st["last_line"] = "A"
                    st["last_line_frame"] = frame_idx
                    st["line_a_frame"] = frame_idx
            if crossed_b and seq is None:
                if st["last_line"] == "A":
                    seq = "A_TO_B"
                    st["line_b_frame"] = frame_idx
                else:
                    st["last_line"] = "B"
                    st["last_line_frame"] = frame_idx
                    st["line_b_frame"] = frame_idx

            if seq is None:
                continue

            age_frames = frame_idx - st["first_frame"] + 1
            displacement = _distance(st["first_pos"], curr)
            gap = frame_idx - (st["last_line_frame"] or frame_idx)

            if age_frames < self.cfg.min_age_frames:
                continue
            if displacement < self.cfg.min_displacement_px:
                continue
            if gap > self.cfg.max_gap_frames:
                continue

            direction_label = self.cfg.direction_labels.get(
                "a_to_b" if seq == "A_TO_B" else "b_to_a",
                seq,
            )
            events.append(
                CountEvent(
                    track_id=tv.vehicle_id,
                    direction=seq,
                    direction_label=direction_label,
                    timestamp=time.time(),
                    counting_mode="gate",
                    gate_sequence=seq,
                    line_a_cross_frame=st["line_a_frame"],
                    line_b_cross_frame=st["line_b_frame"],
                    track_age_frames=age_frames,
                    track_displacement_px=displacement,
                )
            )
            st["counted"] = True
            tv.has_been_counted = True

        return events

    @staticmethod
    def _crossed_line(prev: Tuple[float, float], curr: Tuple[float, float], line: List[Tuple[int, int]]) -> bool:
        p1, p2 = line
        s1 = _side_of_line(prev, p1, p2)
        s2 = _side_of_line(curr, p1, p2)
        if s1 == 0 or s2 == 0:
            return False
        if s1 * s2 > 0:
            return False
        return _segments_intersect(prev, curr, p1, p2)


