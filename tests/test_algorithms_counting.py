"""
Tests for counting algorithms.
"""

import time
import pytest
from collections import deque
from dataclasses import dataclass
from typing import Optional

from algorithms.counting.base import Counter, CounterConfig
from algorithms.counting.line import (
    LineCounter,
    LineCounterConfig,
    _side_of_line,
    _crossed_line,
    _distance,
)


@dataclass
class MockTrack:
    """Mock track for testing counting algorithms."""
    vehicle_id: int
    trajectory: deque
    bbox: tuple = (0, 0, 50, 50)
    center: tuple = (25, 25)
    frames_since_seen: int = 0
    direction: Optional[str] = None
    has_been_counted: bool = False


class TestCounterBase:
    def test_counter_config_defaults(self):
        config = CounterConfig()
        assert config.direction_labels["a_to_b"] == "northbound"
        assert config.min_trajectory_length == 2

    def test_counted_tracking(self):
        """Counter tracks counted IDs without modifying tracks."""
        config = LineCounterConfig(
            line_a=[(0, 50), (100, 50)],
            line_b=[(0, 150), (100, 150)],
        )
        counter = LineCounter(config)
        
        assert not counter.is_counted(1)
        counter.mark_counted(1)
        assert counter.is_counted(1)
        assert 1 in counter.get_counted_ids()
        
        counter.reset()
        assert not counter.is_counted(1)


class TestLineHelpers:
    def test_side_of_line(self):
        # Horizontal line from (0,100) to (200,100)
        line_a = (0, 100)
        line_b = (200, 100)
        
        # Point above line
        assert _side_of_line((100, 50), line_a, line_b) < 0
        # Point below line
        assert _side_of_line((100, 150), line_a, line_b) > 0
        # Point on line
        assert _side_of_line((100, 100), line_a, line_b) == 0

    def test_crossed_line_true(self):
        line = [(0, 100), (200, 100)]
        # Movement from above to below
        assert _crossed_line((100, 50), (100, 150), line) is True

    def test_crossed_line_false_same_side(self):
        line = [(0, 100), (200, 100)]
        # Movement staying above
        assert _crossed_line((100, 50), (100, 80), line) is False

    def test_crossed_line_false_empty(self):
        assert _crossed_line((100, 50), (100, 150), []) is False
        assert _crossed_line((100, 50), (100, 150), None) is False

    def test_distance(self):
        assert _distance((0, 0), (3, 4)) == 5.0
        assert _distance((10, 10), (10, 10)) == 0.0


class TestLineCounter:
    def _create_counter(self):
        """Create a LineCounter with two horizontal lines."""
        config = LineCounterConfig(
            direction_labels={"a_to_b": "northbound", "b_to_a": "southbound"},
            line_a=[(0, 100), (200, 100)],  # Line A at y=100
            line_b=[(0, 200), (200, 200)],  # Line B at y=200
            max_gap_frames=30,
            min_age_frames=2,
            min_displacement_px=10.0,
        )
        return LineCounter(config)

    def test_no_events_insufficient_trajectory(self):
        """No events when trajectory has < 2 points."""
        counter = self._create_counter()
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50)]),  # Only 1 point
        )
        
        events = counter.process([track], frame_idx=1)
        assert len(events) == 0

    def test_no_events_no_crossing(self):
        """No events when track doesn't cross any line."""
        counter = self._create_counter()
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50), (100, 60), (100, 70)]),  # Stays above both
        )
        
        events = counter.process([track], frame_idx=10)
        assert len(events) == 0

    def test_a_to_b_crossing(self):
        """Detect A->B crossing sequence."""
        counter = self._create_counter()
        
        # Start above line A
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50), (100, 90)]),
        )
        events = counter.process([track], frame_idx=1)
        assert len(events) == 0  # Crossed A but not B yet
        
        # Cross line A (above to below)
        track.trajectory.append((100, 110))
        events = counter.process([track], frame_idx=2)
        assert len(events) == 0  # Crossed A, waiting for B
        
        # Move toward B
        track.trajectory.append((100, 190))
        events = counter.process([track], frame_idx=3)
        assert len(events) == 0  # Approaching B
        
        # Cross line B
        track.trajectory.append((100, 210))
        events = counter.process([track], frame_idx=4)
        assert len(events) == 1
        assert events[0].direction == "A_TO_B"
        assert events[0].direction_label == "northbound"
        assert events[0].track_id == 1

    def test_b_to_a_crossing(self):
        """Detect B->A crossing sequence."""
        counter = self._create_counter()
        
        # Start below line B
        track = MockTrack(
            vehicle_id=2,
            trajectory=deque([(100, 250), (100, 210)]),
        )
        events = counter.process([track], frame_idx=1)
        assert len(events) == 0
        
        # Cross line B
        track.trajectory.append((100, 190))
        events = counter.process([track], frame_idx=2)
        assert len(events) == 0  # Crossed B, waiting for A
        
        # Move toward A
        track.trajectory.append((100, 110))
        events = counter.process([track], frame_idx=3)
        assert len(events) == 0
        
        # Cross line A
        track.trajectory.append((100, 90))
        events = counter.process([track], frame_idx=4)
        assert len(events) == 1
        assert events[0].direction == "B_TO_A"
        assert events[0].direction_label == "southbound"

    def test_track_not_modified(self):
        """Counter does NOT modify track objects."""
        counter = self._create_counter()
        
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50)]),
            has_been_counted=False,
        )
        
        # Simulate frame-by-frame processing
        positions = [(100, 90), (100, 110), (100, 190), (100, 210)]
        all_events = []
        for i, pos in enumerate(positions):
            track.trajectory.append(pos)
            events = counter.process([track], frame_idx=i + 1)
            all_events.extend(events)
        
        # Should have counted
        assert len(all_events) == 1
        
        # Track should NOT be modified by counter
        assert track.has_been_counted is False
        assert track.direction is None
        
        # But counter knows it's counted
        assert counter.is_counted(1)

    def test_min_age_constraint(self):
        """Track must exist for min_age_frames before counting."""
        config = LineCounterConfig(
            line_a=[(0, 100), (200, 100)],
            line_b=[(0, 200), (200, 200)],
            min_age_frames=5,  # Require 5 frames
            min_displacement_px=0,
        )
        counter = LineCounter(config)
        
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50), (100, 110), (100, 190), (100, 210)]),
        )
        
        # Process at frame 3 (age = 3, less than min_age_frames=5)
        events = counter.process([track], frame_idx=3)
        assert len(events) == 0  # Rejected due to age

    def test_min_displacement_constraint(self):
        """Track must have min displacement before counting."""
        config = LineCounterConfig(
            line_a=[(0, 100), (200, 100)],
            line_b=[(0, 200), (200, 200)],
            min_age_frames=1,
            min_displacement_px=500,  # Require large displacement
        )
        counter = LineCounter(config)
        
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50), (100, 110), (100, 190), (100, 210)]),  # ~160px displacement
        )
        
        events = counter.process([track], frame_idx=10)
        assert len(events) == 0  # Rejected due to displacement

    def test_get_lines(self):
        """get_lines returns line segments for visualization."""
        counter = self._create_counter()
        lines = counter.get_lines()
        
        assert len(lines) == 2
        assert lines[0] == ((0, 100), (200, 100))
        assert lines[1] == ((0, 200), (200, 200))

    def test_already_counted_skipped(self):
        """Track already counted is skipped."""
        counter = self._create_counter()
        
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50)]),
        )
        
        # Simulate frame-by-frame crossing
        positions = [(100, 90), (100, 110), (100, 190), (100, 210)]
        all_events = []
        for i, pos in enumerate(positions):
            track.trajectory.append(pos)
            events = counter.process([track], frame_idx=i + 1)
            all_events.extend(events)
        
        # Should have counted once
        assert len(all_events) == 1
        
        # Add more trajectory and try again - should be skipped
        track.trajectory.append((100, 250))
        events = counter.process([track], frame_idx=10)
        assert len(events) == 0  # Already counted

