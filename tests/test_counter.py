"""
Tests for counting strategies (GateCounter and LineCounter).
"""

import math
import pytest
from collections import deque

from algorithms.counting.gate import GateCounter, GateCounterConfig
from algorithms.counting.line import LineCounter, LineCounterConfig
from detection.tracker import TrackedVehicle


def _tv(track_id: int, points):
    """Create a TrackedVehicle for testing."""
    return TrackedVehicle(
        vehicle_id=track_id,
        bbox=(0, 0, 0, 0),
        center=points[-1],
        frames_since_seen=0,
        direction=None,
        has_been_counted=False,
        trajectory=deque(points, maxlen=20),
    )


class TestGateCounter:
    """Tests for two-line gate counting (default strategy)."""

    def test_gate_counter_sequence_a_to_b(self):
        """Track crossing A then B produces A_TO_B event."""
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
        assert ev.direction == "A_TO_B"
        assert ev.direction_label == "northbound"
        assert ev.counting_mode == "gate"

    def test_gate_counter_sequence_b_to_a(self):
        """Track crossing B then A produces B_TO_A event."""
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

        # Cross B then A
        tv1 = _tv(1, [(5, -2), (5, 2)])  # crosses B
        events = counter.process([tv1], frame_idx=1)
        assert len(events) == 0

        tv1_next = _tv(1, [(5, 2), (5, 12)])  # crosses A
        events = counter.process([tv1_next], frame_idx=2)
        assert len(events) == 1
        ev = events[0]
        assert ev.gate_sequence == "B_TO_A"
        assert ev.direction == "B_TO_A"
        assert ev.direction_label == "southbound"

    def test_gate_counter_only_counts_once(self):
        """Each track is counted only once."""
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

        # Cross A then B
        tv1 = _tv(1, [(5, 12), (5, 8)])
        counter.process([tv1], frame_idx=1)
        tv1_next = _tv(1, [(5, 8), (5, -2)])
        events = counter.process([tv1_next], frame_idx=2)
        assert len(events) == 1

        # Try to cross again - should not count
        tv1_again = _tv(1, [(5, -2), (5, 12)])
        events = counter.process([tv1_again], frame_idx=3)
        assert len(events) == 0


class TestLineCounter:
    """Tests for single-line counting (fallback strategy)."""

    def test_line_counter_maps_to_a_to_b(self):
        """Crossing from negative side to positive side maps to A_TO_B."""
        line = [(0, 10), (10, 10)]
        counter = LineCounter(
            LineCounterConfig(
                line=line,
                direction_labels={"a_to_b": "northbound", "b_to_a": "southbound"},
                min_age_frames=1,
                min_displacement_px=1.0,
            )
        )

        # Cross from negative side (above) to positive side (below) = A_TO_B
        tv1 = _tv(1, [(5, 8), (5, 12)])
        events = counter.process([tv1], frame_idx=1)
        assert len(events) == 1
        ev = events[0]
        assert ev.direction == "A_TO_B"  # Mapped from "positive" (started on negative side)
        assert ev.direction_label == "northbound"
        assert ev.counting_mode == "line"

    def test_line_counter_maps_to_b_to_a(self):
        """Crossing from positive side to negative side maps to B_TO_A."""
        line = [(0, 10), (10, 10)]
        counter = LineCounter(
            LineCounterConfig(
                line=line,
                direction_labels={"a_to_b": "northbound", "b_to_a": "southbound"},
                min_age_frames=1,
                min_displacement_px=1.0,
            )
        )

        # Cross from positive side (below) to negative side (above) = B_TO_A
        tv1 = _tv(1, [(5, 12), (5, 8)])
        events = counter.process([tv1], frame_idx=1)
        assert len(events) == 1
        ev = events[0]
        assert ev.direction == "B_TO_A"  # Mapped from "negative" (started on positive side)
        assert ev.direction_label == "southbound"

    def test_line_counter_only_counts_once(self):
        """Each track is counted only once."""
        line = [(0, 10), (10, 10)]
        counter = LineCounter(
            LineCounterConfig(
                line=line,
                direction_labels={"a_to_b": "northbound", "b_to_a": "southbound"},
                min_age_frames=1,
                min_displacement_px=1.0,
            )
        )

        tv1 = _tv(1, [(5, 12), (5, 8)])
        events = counter.process([tv1], frame_idx=1)
        assert len(events) == 1

        # Try to cross again
        tv1_again = _tv(1, [(5, 8), (5, 12)])
        events = counter.process([tv1_again], frame_idx=2)
        assert len(events) == 0  # Already counted
