"""
Gate-based counting algorithm (two-line gate).

Counts when a track crosses line A then line B (A_TO_B) or B then A (B_TO_A)
within max_gap_frames. Enforces min_age_frames and min_displacement_px.
Each track is counted only once.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from models.count_event import CountEvent
from .base import Counter, CounterConfig


def _side_of_line(p: Tuple[float, float], a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """Signed area (cross product) to determine which side of a->b the point lies on."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _segments_intersect(
    p1: Tuple[float, float], 
    p2: Tuple[float, float], 
    a: Tuple[int, int], 
    b: Tuple[int, int]
) -> bool:
    """Check if segment p1->p2 intersects with segment a->b (inclusive)."""
    def orient(x, y, z):
        return (y[0] - x[0]) * (z[1] - x[1]) - (y[1] - x[1]) * (z[0] - x[0])

    o1 = orient(p1, p2, a)
    o2 = orient(p1, p2, b)
    o3 = orient(a, b, p1)
    o4 = orient(a, b, p2)

    if o1 == 0 and o2 == 0 and o3 == 0 and o4 == 0:
        return False  # colinear overlap not expected; treat as no crossing

    return (o1 * o2 <= 0) and (o3 * o4 <= 0)


def _distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Euclidean distance between two points."""
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def crossed_line(
    prev: Tuple[float, float], 
    curr: Tuple[float, float], 
    line: List[Tuple[int, int]]
) -> bool:
    """
    Check if movement from prev to curr crosses the line.
    
    Args:
        prev: Previous position (x, y).
        curr: Current position (x, y).
        line: Line as [(x1, y1), (x2, y2)].
        
    Returns:
        True if the movement crosses the line.
    """
    if not line or len(line) != 2:
        return False
    p1, p2 = line
    s1 = _side_of_line(prev, p1, p2)
    s2 = _side_of_line(curr, p1, p2)
    if s1 == 0 or s2 == 0:
        return False
    if s1 * s2 > 0:
        return False
    return _segments_intersect(prev, curr, p1, p2)


@dataclass
class GateCounterConfig(CounterConfig):
    """
    Configuration for gate-based (two-line) counting.
    
    Attributes:
        line_a: First gate line as [(x1,y1), (x2,y2)] in pixels.
        line_b: Second gate line as [(x1,y1), (x2,y2)] in pixels.
        max_gap_frames: Max frames between crossing line A and line B for valid count.
        min_age_frames: Min track age (frames) before counting is allowed.
        min_displacement_px: Min displacement (pixels) from first to current position.
    """
    line_a: List[Tuple[int, int]] = field(default_factory=list)
    line_b: List[Tuple[int, int]] = field(default_factory=list)
    max_gap_frames: int = 30
    min_age_frames: int = 3
    min_displacement_px: float = 15.0


@dataclass
class _GateTrackState:
    """Internal state for tracking gate crossings per track."""
    first_frame: int
    first_pos: Tuple[float, float]
    last_crossed_line: Optional[str] = None  # "A" or "B"
    last_crossed_frame: Optional[int] = None
    line_a_frame: Optional[int] = None
    line_b_frame: Optional[int] = None


class GateCounter(Counter):
    """
    Two-line gate counter that detects A->B and B->A crossing sequences.
    
    A count is registered when:
    1. Track crosses line A, then crosses line B within max_gap_frames -> A_TO_B
    2. Track crosses line B, then crosses line A within max_gap_frames -> B_TO_A
    
    Additional constraints:
    - Track must be at least min_age_frames old
    - Track must have moved at least min_displacement_px from start
    - Each track is counted only once
    
    This counter does NOT modify track objects.
    """

    def __init__(self, config: GateCounterConfig):
        super().__init__(config)
        self._gate_config = config
        self._track_states: Dict[int, _GateTrackState] = {}
        
        # Platform metadata (set via set_metadata())
        self._detection_backend = "unknown"
        self._platform = None
        self._process_pid = None

    @property
    def line_a(self) -> List[Tuple[int, int]]:
        """Gate line A."""
        return self._gate_config.line_a

    @property
    def line_b(self) -> List[Tuple[int, int]]:
        """Gate line B."""
        return self._gate_config.line_b

    @property
    def max_gap_frames(self) -> int:
        """Maximum frames between line crossings."""
        return self._gate_config.max_gap_frames

    @property
    def min_age_frames(self) -> int:
        """Minimum track age before counting."""
        return self._gate_config.min_age_frames

    @property
    def min_displacement_px(self) -> float:
        """Minimum displacement for valid count."""
        return self._gate_config.min_displacement_px

    def get_lines(self) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """Get counting lines for visualization."""
        lines = []
        if self.line_a and len(self.line_a) == 2:
            lines.append((self.line_a[0], self.line_a[1]))
        if self.line_b and len(self.line_b) == 2:
            lines.append((self.line_b[0], self.line_b[1]))
        return lines

    def process(self, tracks: List[Any], frame_idx: int) -> List[CountEvent]:
        """
        Process tracks and detect gate crossings.
        
        A gate crossing is detected when:
        - Track crosses A then B (A_TO_B) within max_gap_frames
        - Track crosses B then A (B_TO_A) within max_gap_frames
        
        Args:
            tracks: List of track objects with vehicle_id, trajectory attributes.
            frame_idx: Current frame index.
            
        Returns:
            List of CountEvent for tracks that completed a gate crossing.
        """
        events: List[CountEvent] = []
        
        # Validate lines exist
        if not self.line_a or not self.line_b:
            return events
        if len(self.line_a) != 2 or len(self.line_b) != 2:
            return events

        for track in tracks:
            event = self._process_track(track, frame_idx)
            if event is not None:
                events.append(event)
        
        return events

    def _process_track(self, track: Any, frame_idx: int) -> Optional[CountEvent]:
        """Process a single track for gate crossing."""
        track_id = track.vehicle_id
        trajectory = list(track.trajectory)
        
        # Skip if already counted
        if self.is_counted(track_id):
            return None
        
        # Need at least 2 trajectory points to detect crossing
        if len(trajectory) < 2:
            return None
        
        # Get or create track state
        if track_id not in self._track_states:
            self._track_states[track_id] = _GateTrackState(
                first_frame=frame_idx,
                first_pos=trajectory[0],
            )
        st = self._track_states[track_id]
        
        # Get last two positions for crossing detection
        prev = trajectory[-2]
        curr = trajectory[-1]
        
        # Check for line crossings this frame
        crossed_a = crossed_line(prev, curr, self.line_a)
        crossed_b = crossed_line(prev, curr, self.line_b)
        
        # Determine if we completed a gate sequence
        sequence = self._update_crossing_state(st, crossed_a, crossed_b, frame_idx)
        
        if sequence is None:
            return None
        
        # Validate constraints
        age_frames = frame_idx - st.first_frame + 1
        displacement = _distance(st.first_pos, curr)
        
        # Check gap constraint (time since first line crossing)
        first_line_frame = st.line_a_frame if sequence == "A_TO_B" else st.line_b_frame
        second_line_frame = st.line_b_frame if sequence == "A_TO_B" else st.line_a_frame
        gap = second_line_frame - first_line_frame if first_line_frame and second_line_frame else 0
        
        if age_frames < self.min_age_frames:
            return None
        if displacement < self.min_displacement_px:
            return None
        if gap > self.max_gap_frames:
            # Reset state - crossing took too long
            st.last_crossed_line = None
            st.last_crossed_frame = None
            return None
        
        # Get direction label
        direction_label = self.direction_labels.get(
            "a_to_b" if sequence == "A_TO_B" else "b_to_a",
            sequence,
        )
        
        # Extract detection metadata from track
        class_id = getattr(track, 'class_id', None)
        class_name = getattr(track, 'class_name', None)
        confidence = getattr(track, 'confidence', 1.0)
        
        # Create count event
        event = CountEvent(
            track_id=track_id,
            direction=sequence,
            direction_label=direction_label,
            timestamp=time.time(),
            counting_mode="gate",
            gate_sequence=sequence,
            line_a_cross_frame=st.line_a_frame,
            line_b_cross_frame=st.line_b_frame,
            track_age_frames=age_frames,
            track_displacement_px=displacement,
            class_id=class_id,
            class_name=class_name,
            confidence=confidence,
            detection_backend=getattr(self, '_detection_backend', 'unknown'),
            platform=getattr(self, '_platform', None),
            process_pid=getattr(self, '_process_pid', None),
        )
        
        # Mark as counted in counter's internal state
        self.mark_counted(track_id)
        
        # Sync counted flag to track object so tracker can handle it properly
        # This prevents track ID fragmentation from causing double-counts
        if hasattr(track, 'has_been_counted'):
            track.has_been_counted = True
        if hasattr(track, 'direction'):
            track.direction = sequence
        
        import logging
        logging.info(
            f"[COUNT] track_id={track_id} direction={sequence} "
            f"frame={frame_idx} age={age_frames} displacement={displacement:.1f}px"
        )
        
        return event

    def _update_crossing_state(
        self, 
        st: _GateTrackState, 
        crossed_a: bool, 
        crossed_b: bool, 
        frame_idx: int
    ) -> Optional[str]:
        """
        Update crossing state and return completed sequence if any.
        
        Returns:
            "A_TO_B" if crossed A then B, "B_TO_A" if crossed B then A, None otherwise.
        """
        sequence = None
        
        if crossed_a:
            st.line_a_frame = frame_idx
            if st.last_crossed_line == "B":
                # Crossed B first, now crossing A -> B_TO_A
                sequence = "B_TO_A"
            else:
                # First line crossed or was A before
                st.last_crossed_line = "A"
                st.last_crossed_frame = frame_idx
        
        if crossed_b and sequence is None:
            st.line_b_frame = frame_idx
            if st.last_crossed_line == "A":
                # Crossed A first, now crossing B -> A_TO_B
                sequence = "A_TO_B"
            else:
                # First line crossed or was B before
                st.last_crossed_line = "B"
                st.last_crossed_frame = frame_idx
        
        return sequence

    def reset(self) -> None:
        """Reset counter state."""
        super().reset()
        self._track_states.clear()

    def cleanup_stale_tracks(self, active_track_ids: set) -> None:
        """Remove state for tracks no longer active."""
        stale_ids = set(self._track_states.keys()) - active_track_ids
        for track_id in stale_ids:
            del self._track_states[track_id]
    
    def set_metadata(self, detection_backend: str = "unknown", 
                    platform: Optional[str] = None, 
                    process_pid: Optional[int] = None) -> None:
        """
        Set platform metadata for count events.
        
        Args:
            detection_backend: Backend used for detection ("bgsub", "yolo", "hailo").
            platform: Platform string (e.g., "Windows-10", "Linux-6.1.21-rpi").
            process_pid: Process ID creating events.
        """
        self._detection_backend = detection_backend
        self._platform = platform
        self._process_pid = process_pid


def create_gate_counter_from_config(
    counting_cfg: Dict[str, Any],
    frame_width: int,
    frame_height: int,
) -> GateCounter:
    """
    Factory function to create a GateCounter from config dict.
    
    Args:
        counting_cfg: Counting config from YAML.
        frame_width: Frame width for ratio-to-pixel conversion.
        frame_height: Frame height for ratio-to-pixel conversion.
    """
    from algorithms.counting.utils import compute_counting_line
    
    line_a_cfg = counting_cfg.get("line_a")
    line_b_cfg = counting_cfg.get("line_b")
    
    line_a = compute_counting_line(line_a_cfg, frame_width, frame_height) if line_a_cfg else []
    line_b = compute_counting_line(line_b_cfg, frame_width, frame_height) if line_b_cfg else []
    
    direction_labels = counting_cfg.get("direction_labels", {}) or {
        "a_to_b": "northbound",
        "b_to_a": "southbound",
    }
    
    config = GateCounterConfig(
        direction_labels=direction_labels,
        line_a=line_a,
        line_b=line_b,
        max_gap_frames=int(counting_cfg.get("max_gap_frames", 30)),
        min_age_frames=int(counting_cfg.get("min_age_frames", 3)),
        min_displacement_px=float(counting_cfg.get("min_displacement_px", 15.0)),
    )
    
    return GateCounter(config)

