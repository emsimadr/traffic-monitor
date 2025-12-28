import math

import pytest

from analytics.counter import GateCounter, GateCounterConfig
from detection.tracker import TrackedVehicle
from collections import deque


def _tv(track_id: int, points):
    return TrackedVehicle(
        vehicle_id=track_id,
        bbox=(0, 0, 0, 0),
        center=points[-1],
        frames_since_seen=0,
        direction=None,
        has_been_counted=False,
        trajectory=deque(points, maxlen=20),
    )


def test_gate_counter_sequence_a_to_b():
    line_a = [(0, 10), (10, 10)]
    line_b = [(0, 0), (10, 0)]
    counter = GateCounter(
        GateCounterConfig(
            line_a=line_a,
            line_b=line_b,
            direction_labels={"a_to_b": "northbound", "b_to_a": "southbound"},
            max_gap_frames=10,
            min_age_frames=1,
            min_displacement_px=1.0,
        )
    )

    # Cross A then B across frames
    tv1 = _tv(1, [(5, 12), (5, 8)])  # crosses A
    events = counter.process([tv1], frame_idx=1)
    assert len(events) == 0

    tv1_next = _tv(1, [(5, 8), (5, -2)])  # crosses B
    events = counter.process([tv1_next], frame_idx=2)
    assert len(events) == 1
    ev = events[0]
    assert ev.gate_sequence == "A_TO_B"
    assert ev.direction_label == "northbound"
    assert ev.counting_mode == "gate"
    assert ev.line_a_cross_frame is not None or ev.line_b_cross_frame is not None


