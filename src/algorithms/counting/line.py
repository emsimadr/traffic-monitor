"""
Line-based counting algorithm (two-line gate).

This preserves the exact behavior of the original GateCounter while
conforming to the Counter interface. Tracks are NOT modified.
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


def _crossed_line(
    prev: Tuple[float, float], 
    curr: Tuple[float, float], 
    line: List[Tuple[int, int]]
) -> bool:
    """Check if movement from prev to curr crosses the line."""
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
class LineCounterConfig(CounterConfig):
    """
    Configuration for line-based (two-line gate) counting.
    
    Attributes:
        line_a: First gate line as [(x1,y1), (x2,y2)] in pixels.
        line_b: Second gate line as [(x1,y1), (x2,y2)] in pixels.
        max_gap_frames: Max frames between line crossings for valid count.
        min_age_frames: Min track age (frames) before counting.
        min_displacement_px: Min displacement (pixels) for valid count.
    """
    line_a: List[Tuple[int, int]] = field(default_factory=list)
    line_b: List[Tuple[int, int]] = field(default_factory=list)
    max_gap_frames: int = 30
    min_age_frames: int = 3
    min_displacement_px: float = 15.0


@dataclass
class _TrackState:
    """Internal state for tracking line crossings per track."""
    first_frame: int
    first_pos: Tuple[float, float]
    last_line: Optional[str] = None
    last_line_frame: Optional[int] = None
    line_a_frame: Optional[int] = None
    line_b_frame: Optional[int] = None


class LineCounter(Counter):
    """
    Two-line gate counter that detects A->B and B->A crossings.
    
    This is the refactored version of GateCounter that:
    - Does NOT modify track objects
    - Maintains internal state for crossing detection
    - Conforms to the Counter interface
    
    The counting logic is preserved exactly from the original implementation.
    """

    def __init__(self, config: LineCounterConfig):
        super().__init__(config)
        self._line_config = config
        self._track_states: Dict[int, _TrackState] = {}

    @property
    def line_a(self) -> List[Tuple[int, int]]:
        return self._line_config.line_a

    @property
    def line_b(self) -> List[Tuple[int, int]]:
        return self._line_config.line_b

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
        Process tracks and detect line crossings.
        
        Args:
            tracks: List of track objects with vehicle_id, trajectory attributes.
            frame_idx: Current frame index.
            
        Returns:
            List of CountEvent for tracks that completed a gate crossing.
        """
        events: List[CountEvent] = []
        
        # Validate lines
        if not self.line_a or not self.line_b:
            return events
        if len(self.line_a) != 2 or len(self.line_b) != 2:
            return events

        for track in tracks:
            # Get track ID and trajectory
            track_id = track.vehicle_id
            trajectory = list(track.trajectory)
            
            # Skip if already counted
            if self.is_counted(track_id):
                continue
            
            # Need at least 2 trajectory points
            if len(trajectory) < 2:
                continue
            
            # Get or create track state
            if track_id not in self._track_states:
                self._track_states[track_id] = _TrackState(
                    first_frame=frame_idx,
                    first_pos=trajectory[0],
                )
            st = self._track_states[track_id]
            
            # Get last two positions
            prev = trajectory[-2]
            curr = trajectory[-1]
            
            # Check for line crossings
            crossed_a = _crossed_line(prev, curr, self.line_a)
            crossed_b = _crossed_line(prev, curr, self.line_b)
            
            # Determine crossing sequence
            seq = None
            if crossed_a:
                if st.last_line == "B":
                    seq = "B_TO_A"
                    st.line_a_frame = frame_idx
                else:
                    st.last_line = "A"
                    st.last_line_frame = frame_idx
                    st.line_a_frame = frame_idx
            
            if crossed_b and seq is None:
                if st.last_line == "A":
                    seq = "A_TO_B"
                    st.line_b_frame = frame_idx
                else:
                    st.last_line = "B"
                    st.last_line_frame = frame_idx
                    st.line_b_frame = frame_idx
            
            if seq is None:
                continue
            
            # Validate crossing constraints
            age_frames = frame_idx - st.first_frame + 1
            displacement = _distance(st.first_pos, curr)
            gap = frame_idx - (st.last_line_frame or frame_idx)
            
            if age_frames < self._line_config.min_age_frames:
                continue
            if displacement < self._line_config.min_displacement_px:
                continue
            if gap > self._line_config.max_gap_frames:
                continue
            
            # Get direction label
            direction_label = self.direction_labels.get(
                "a_to_b" if seq == "A_TO_B" else "b_to_a",
                seq,
            )
            
            # Create count event
            event = CountEvent(
                track_id=track_id,
                direction=seq,
                direction_label=direction_label,
                timestamp=time.time(),
                counting_mode="gate",
                gate_sequence=seq,
                line_a_cross_frame=st.line_a_frame,
                line_b_cross_frame=st.line_b_frame,
                track_age_frames=age_frames,
                track_displacement_px=displacement,
            )
            events.append(event)
            
            # Mark as counted (internal state only - NOT modifying track)
            self.mark_counted(track_id)
        
        return events

    def reset(self) -> None:
        """Reset counter state."""
        super().reset()
        self._track_states.clear()


def create_line_counter_from_config(
    counting_cfg: Dict[str, Any],
    frame_width: int,
    frame_height: int,
) -> LineCounter:
    """
    Factory function to create a LineCounter from config dict.
    
    Args:
        counting_cfg: Counting config from YAML (with line_a, line_b, etc.)
        frame_width: Frame width for ratio-to-pixel conversion.
        frame_height: Frame height for ratio-to-pixel conversion.
    """
    from analytics.counting import compute_counting_line
    
    line_a_cfg = counting_cfg.get("line_a")
    line_b_cfg = counting_cfg.get("line_b")
    
    line_a = compute_counting_line(line_a_cfg, frame_width, frame_height) if line_a_cfg else []
    line_b = compute_counting_line(line_b_cfg, frame_width, frame_height) if line_b_cfg else []
    
    direction_labels = counting_cfg.get("direction_labels", {}) or {
        "a_to_b": "northbound",
        "b_to_a": "southbound",
    }
    
    gate_params = counting_cfg.get("gate", {}) or {}
    
    config = LineCounterConfig(
        direction_labels=direction_labels,
        line_a=line_a,
        line_b=line_b,
        max_gap_frames=int(gate_params.get("max_gap_frames", 30)),
        min_age_frames=int(gate_params.get("min_age_frames", 3)),
        min_displacement_px=float(gate_params.get("min_displacement_px", 15.0)),
    )
    
    return LineCounter(config)

