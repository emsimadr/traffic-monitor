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
    crossed_line as line_crossed_line,
)
from algorithms.counting.gate import (
    GateCounter,
    GateCounterConfig,
    crossed_line as gate_crossed_line,
    _side_of_line,
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
        config = GateCounterConfig(
            line_a=[(0, 50), (100, 50)],
            line_b=[(0, 150), (100, 150)],
        )
        counter = GateCounter(config)
        
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
        # Movement from above to below (gate version returns bool)
        assert gate_crossed_line((100, 50), (100, 150), line) is True

    def test_crossed_line_false_same_side(self):
        line = [(0, 100), (200, 100)]
        # Movement staying above
        assert gate_crossed_line((100, 50), (100, 80), line) is False

    def test_crossed_line_false_empty(self):
        assert gate_crossed_line((100, 50), (100, 150), []) is False
        assert gate_crossed_line((100, 50), (100, 150), None) is False

    def test_distance(self):
        assert _distance((0, 0), (3, 4)) == 5.0
        assert _distance((10, 10), (10, 10)) == 0.0
    
    def test_line_crossed_returns_direction(self):
        """LineCounter's crossed_line returns direction string."""
        line = [(0, 100), (200, 100)]
        # Movement from above (negative side) to below (positive side)
        result = line_crossed_line((100, 50), (100, 150), line)
        assert result in ("positive", "negative")
        
        # Movement staying above - no crossing
        result = line_crossed_line((100, 50), (100, 80), line)
        assert result is None


class TestLineCounter:
    """Tests for single-line counter."""
    
    def _create_counter(self):
        """Create a LineCounter with a horizontal line."""
        config = LineCounterConfig(
            direction_labels={"positive": "inbound", "negative": "outbound"},
            line=[(0, 100), (200, 100)],  # Line at y=100
            min_age_frames=2,
            min_displacement_px=10.0,
        )
        return LineCounter(config)

    def test_no_events_insufficient_trajectory(self):
        """No events when trajectory has < 2 points."""
        counter = self._create_counter()
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50)]),
        )
        
        events = counter.process([track], frame_idx=1)
        assert len(events) == 0

    def test_no_events_no_crossing(self):
        """No events when track doesn't cross the line."""
        counter = self._create_counter()
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50), (100, 60), (100, 70)]),  # Stays above
        )
        
        events = counter.process([track], frame_idx=10)
        assert len(events) == 0

    def test_crossing_detected(self):
        """Detect single line crossing."""
        counter = self._create_counter()
        
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50)]),
        )
        
        # Cross the line from above to below
        track.trajectory.append((100, 90))
        events = counter.process([track], frame_idx=1)
        assert len(events) == 0  # Haven't crossed yet
        
        track.trajectory.append((100, 110))
        events = counter.process([track], frame_idx=2)
        assert len(events) == 1
        assert events[0].counting_mode == "line"
        assert events[0].track_id == 1

    def test_get_lines(self):
        """get_lines returns single line for visualization."""
        counter = self._create_counter()
        lines = counter.get_lines()
        
        assert len(lines) == 1
        assert lines[0] == ((0, 100), (200, 100))


class TestGateCounter:
    """Tests for two-line gate counter."""
    
    def _create_counter(self):
        """Create a GateCounter with two horizontal lines."""
        config = GateCounterConfig(
            direction_labels={"a_to_b": "northbound", "b_to_a": "southbound"},
            line_a=[(0, 100), (200, 100)],  # Line A at y=100
            line_b=[(0, 200), (200, 200)],  # Line B at y=200
            max_gap_frames=30,
            min_age_frames=2,
            min_displacement_px=10.0,
        )
        return GateCounter(config)

    def test_no_events_insufficient_trajectory(self):
        """No events when trajectory has < 2 points."""
        counter = self._create_counter()
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50)]),
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
        assert len(events) == 0  # Haven't crossed A yet
        
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
        assert events[0].counting_mode == "gate"

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
        config = GateCounterConfig(
            line_a=[(0, 100), (200, 100)],
            line_b=[(0, 200), (200, 200)],
            min_age_frames=5,  # Require 5 frames
            min_displacement_px=0,
        )
        counter = GateCounter(config)
        
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50), (100, 110), (100, 190), (100, 210)]),
        )
        
        # Process at frame 3 (age = 3, less than min_age_frames=5)
        events = counter.process([track], frame_idx=3)
        assert len(events) == 0  # Rejected due to age

    def test_min_displacement_constraint(self):
        """Track must have min displacement before counting."""
        config = GateCounterConfig(
            line_a=[(0, 100), (200, 100)],
            line_b=[(0, 200), (200, 200)],
            min_age_frames=1,
            min_displacement_px=500,  # Require large displacement
        )
        counter = GateCounter(config)
        
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50), (100, 110), (100, 190), (100, 210)]),  # ~160px displacement
        )
        
        events = counter.process([track], frame_idx=10)
        assert len(events) == 0  # Rejected due to displacement

    def test_max_gap_frames_constraint(self):
        """Crossing must complete within max_gap_frames."""
        config = GateCounterConfig(
            line_a=[(0, 100), (200, 100)],
            line_b=[(0, 200), (200, 200)],
            max_gap_frames=5,  # Small gap
            min_age_frames=1,
            min_displacement_px=0,
        )
        counter = GateCounter(config)
        
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50)]),
        )
        
        # Cross line A at frame 1
        track.trajectory.append((100, 110))
        events = counter.process([track], frame_idx=1)
        assert len(events) == 0
        
        # Stay between lines for many frames
        for frame in range(2, 10):
            track.trajectory.append((100, 150))
            events = counter.process([track], frame_idx=frame)
        
        # Cross line B at frame 10 (gap = 9 > max_gap_frames=5)
        track.trajectory.append((100, 210))
        events = counter.process([track], frame_idx=10)
        assert len(events) == 0  # Rejected due to gap

    def test_get_lines(self):
        """get_lines returns both line segments for visualization."""
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

    def test_crossing_a_only_no_count(self):
        """Crossing only line A does not count."""
        counter = self._create_counter()
        
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 50)]),
        )
        
        # Cross line A
        track.trajectory.append((100, 110))
        events = counter.process([track], frame_idx=1)
        assert len(events) == 0
        
        # Stay between lines without crossing B
        for frame in range(2, 10):
            track.trajectory.append((100, 150))
            events = counter.process([track], frame_idx=frame)
            assert len(events) == 0

    def test_crossing_b_only_no_count(self):
        """Crossing only line B does not count."""
        counter = self._create_counter()
        
        track = MockTrack(
            vehicle_id=1,
            trajectory=deque([(100, 150)]),  # Start between lines
        )
        
        # Cross line B
        track.trajectory.append((100, 210))
        events = counter.process([track], frame_idx=1)
        assert len(events) == 0
        
        # Stay below B without crossing A
        for frame in range(2, 10):
            track.trajectory.append((100, 250))
            events = counter.process([track], frame_idx=frame)
            assert len(events) == 0

    def test_multiple_tracks_independent(self):
        """Multiple tracks are counted independently."""
        counter = self._create_counter()
        
        track1 = MockTrack(vehicle_id=1, trajectory=deque([(100, 50)]))
        track2 = MockTrack(vehicle_id=2, trajectory=deque([(150, 250)]))
        
        # Track 1 crosses A
        track1.trajectory.append((100, 110))
        events = counter.process([track1, track2], frame_idx=1)
        assert len(events) == 0
        
        # Track 2 crosses B
        track2.trajectory.append((150, 190))
        events = counter.process([track1, track2], frame_idx=2)
        assert len(events) == 0
        
        # Track 1 crosses B (A->B complete)
        track1.trajectory.append((100, 210))
        events = counter.process([track1, track2], frame_idx=3)
        assert len(events) == 1
        assert events[0].track_id == 1
        assert events[0].direction == "A_TO_B"
        
        # Track 2 crosses A (B->A complete)
        track2.trajectory.append((150, 90))
        events = counter.process([track1, track2], frame_idx=4)
        assert len(events) == 1
        assert events[0].track_id == 2
        assert events[0].direction == "B_TO_A"

