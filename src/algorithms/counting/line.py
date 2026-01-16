"""
Single-line counting algorithm (fallback strategy).

Use this when a two-line gate is not feasible. For bi-directional streets,
gate counting (gate.py) is preferred as the default strategy.

This counter maps its internal crossing directions to A_TO_B/B_TO_A codes
for consistency with the database schema and API responses.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from models.count_event import CountEvent
from .base import Counter, CounterConfig


# Direction code mapping: line crossing side -> standard direction code
# "positive" (crossed from - to + side) maps to A_TO_B
# "negative" (crossed from + to - side) maps to B_TO_A
_DIRECTION_CODE_MAP = {
    "positive": "A_TO_B",
    "negative": "B_TO_A",
}


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
) -> Optional[str]:
    """
    Check if movement from prev to curr crosses the line.
    
    Returns:
        "positive" if crossed from negative to positive side,
        "negative" if crossed from positive to negative side,
        None if no crossing.
    """
    if not line or len(line) != 2:
        return None
    p1, p2 = line
    s1 = _side_of_line(prev, p1, p2)
    s2 = _side_of_line(curr, p1, p2)
    if s1 == 0 or s2 == 0:
        return None
    if s1 * s2 > 0:
        return None
    if not _segments_intersect(prev, curr, p1, p2):
        return None
    return "positive" if s1 < 0 else "negative"


@dataclass
class LineCounterConfig(CounterConfig):
    """
    Configuration for single-line counting (fallback strategy).
    
    Attributes:
        line: Counting line as [(x1,y1), (x2,y2)] in pixels.
        min_age_frames: Min track age (frames) before counting.
        min_displacement_px: Min displacement (pixels) for valid count.
    """
    line: List[Tuple[int, int]] = field(default_factory=list)
    min_age_frames: int = 3
    min_displacement_px: float = 15.0


@dataclass
class _LineTrackState:
    """Internal state for tracking line crossings per track."""
    first_frame: int
    first_pos: Tuple[float, float]


class LineCounter(Counter):
    """
    Single-line counter (fallback strategy for when gate counting isn't feasible).
    
    Detects crossings of a single line. Direction is determined by which side
    of the line the track came from, then mapped to standard A_TO_B/B_TO_A codes:
    
    - Crossing from negative to positive side -> A_TO_B
    - Crossing from positive to negative side -> B_TO_A
    
    This ensures database and API consistency regardless of counting strategy.
    
    This counter does NOT modify track objects.
    """

    def __init__(self, config: LineCounterConfig):
        super().__init__(config)
        self._line_config = config
        self._track_states: Dict[int, _LineTrackState] = {}
        
        # Platform metadata (set via set_metadata())
        self._detection_backend = "unknown"
        self._platform = None
        self._process_pid = None

    @property
    def line(self) -> List[Tuple[int, int]]:
        return self._line_config.line

    def get_lines(self) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """Get counting lines for visualization."""
        if self.line and len(self.line) == 2:
            return [(self.line[0], self.line[1])]
        return []

    def process(self, tracks: List[Any], frame_idx: int) -> List[CountEvent]:
        """
        Process tracks and detect line crossings.
        
        Args:
            tracks: List of track objects with vehicle_id, trajectory attributes.
            frame_idx: Current frame index.
            
        Returns:
            List of CountEvent for tracks that crossed the line.
        """
        events: List[CountEvent] = []
        
        # Validate line exists
        if not self.line or len(self.line) != 2:
            return events

        for track in tracks:
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
                self._track_states[track_id] = _LineTrackState(
                    first_frame=frame_idx,
                    first_pos=trajectory[0],
                )
            st = self._track_states[track_id]
            
            # Get last two positions
            prev = trajectory[-2]
            curr = trajectory[-1]
            
            # Check for line crossing (returns "positive" or "negative")
            internal_direction = crossed_line(prev, curr, self.line)
            if internal_direction is None:
                continue
            
            # Validate constraints
            age_frames = frame_idx - st.first_frame + 1
            displacement = _distance(st.first_pos, curr)
            
            if age_frames < self._line_config.min_age_frames:
                continue
            if displacement < self._line_config.min_displacement_px:
                continue
            
            # Map internal direction to standard direction code (A_TO_B/B_TO_A)
            direction_code = _DIRECTION_CODE_MAP[internal_direction]
            
            # Get direction label from config
            # Use lowercase key format for config lookup (a_to_b, b_to_a)
            label_key = direction_code.lower()
            direction_label = self.direction_labels.get(label_key, direction_code)
            
            # Extract detection metadata from track
            class_id = getattr(track, 'class_id', None)
            class_name = getattr(track, 'class_name', None)
            confidence = getattr(track, 'confidence', 1.0)
            
            # Create count event with standard direction code
            event = CountEvent(
                track_id=track_id,
                direction=direction_code,  # Always A_TO_B or B_TO_A
                direction_label=direction_label,
                timestamp=time.time(),
                counting_mode="line",
                gate_sequence=None,
                line_a_cross_frame=frame_idx,
                line_b_cross_frame=None,
                track_age_frames=age_frames,
                track_displacement_px=displacement,
                class_id=class_id,
                class_name=class_name,
                confidence=confidence,
                detection_backend=getattr(self, '_detection_backend', 'unknown'),
                platform=getattr(self, '_platform', None),
                process_pid=getattr(self, '_process_pid', None),
            )
            events.append(event)
            
            # Mark as counted in counter's internal state
            self.mark_counted(track_id)
            
            # Sync counted flag to track object so tracker can handle it properly
            # This prevents track ID fragmentation from causing double-counts
            if hasattr(track, 'has_been_counted'):
                track.has_been_counted = True
            if hasattr(track, 'direction'):
                track.direction = direction_code
        
        return events

    def reset(self) -> None:
        """Reset counter state."""
        super().reset()
        self._track_states.clear()
    
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


def create_line_counter_from_config(
    counting_cfg: Dict[str, Any],
    frame_width: int,
    frame_height: int,
) -> LineCounter:
    """
    Factory function to create a LineCounter from config dict.
    
    Args:
        counting_cfg: Counting config from YAML.
        frame_width: Frame width for ratio-to-pixel conversion.
        frame_height: Frame height for ratio-to-pixel conversion.
    """
    from algorithms.counting.utils import compute_counting_line
    
    # Use line_a as the single line for line mode
    line_cfg = counting_cfg.get("line") or counting_cfg.get("line_a")
    line = compute_counting_line(line_cfg, frame_width, frame_height) if line_cfg else []
    
    # Direction labels use standard A_TO_B/B_TO_A keys
    direction_labels = counting_cfg.get("direction_labels", {}) or {
        "a_to_b": "northbound",
        "b_to_a": "southbound",
    }
    
    config = LineCounterConfig(
        direction_labels=direction_labels,
        line=line,
        min_age_frames=int(counting_cfg.get("min_age_frames", 3)),
        min_displacement_px=float(counting_cfg.get("min_displacement_px", 15.0)),
    )
    
    return LineCounter(config)
