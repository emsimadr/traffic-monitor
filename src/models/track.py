"""
Track models for object tracking state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Deque, List, Optional, Tuple

from collections import deque

from .detection import BoundingBox


@dataclass
class Track:
    """
    A tracked object across video frames.
    
    Attributes:
        track_id: Unique identifier for this track.
        bbox: Current bounding box in pixel coordinates.
        center: Current center point (cx, cy).
        frames_since_seen: Frames since last matched detection.
        direction: Direction label (set by counter, not tracker).
        has_been_counted: Whether this track has triggered a count event.
        trajectory: History of center positions (newest last).
        class_id: Optional COCO class ID from detection.
        class_name: Optional human-readable class name.
        confidence: Detection confidence score (0-1).
    """
    track_id: int
    bbox: BoundingBox
    center: Tuple[float, float]
    frames_since_seen: int = 0
    direction: Optional[str] = None
    has_been_counted: bool = False
    trajectory: Deque[Tuple[float, float]] = field(default_factory=lambda: deque(maxlen=20))
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    confidence: float = 1.0

    @classmethod
    def from_tracked_vehicle(cls, tv) -> "Track":
        """
        Adapter: Convert from tracking.tracker.TrackedVehicle to Track.
        
        Args:
            tv: A TrackedVehicle instance from tracking.tracker.
        """
        bbox = tv.bbox  # (x1, y1, x2, y2) tuple
        return cls(
            track_id=tv.vehicle_id,
            bbox=BoundingBox(x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3]),
            center=tv.center,
            frames_since_seen=tv.frames_since_seen,
            direction=tv.direction,
            has_been_counted=tv.has_been_counted,
            trajectory=deque(tv.trajectory, maxlen=20),
            class_id=getattr(tv, "class_id", None),
            class_name=getattr(tv, "class_name", None),
            confidence=getattr(tv, "confidence", 1.0),
        )

    @property
    def age(self) -> int:
        """Number of frames this track has existed (trajectory length)."""
        return len(self.trajectory)

    @property
    def is_active(self) -> bool:
        """Whether this track is still being actively matched."""
        return not self.has_been_counted and self.frames_since_seen == 0


@dataclass(frozen=True)
class TrackState:
    """
    Immutable snapshot of a tracked object (for serialization/API).
    
    Attributes:
        track_id: Unique identifier for this track.
        bbox: Bounding box as (x1, y1, x2, y2) tuple.
        center: Center point (cx, cy).
        direction: Direction label if set.
        has_been_counted: Whether counted.
        class_id: Optional COCO class ID.
        class_name: Optional human-readable class name.
        confidence: Detection confidence score.
    """
    track_id: int
    bbox: Tuple[int, int, int, int]
    center: Tuple[float, float]
    direction: Optional[str] = None
    has_been_counted: bool = False
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    confidence: float = 1.0

    @classmethod
    def from_track(cls, track: Track) -> "TrackState":
        """Create immutable snapshot from a Track."""
        return cls(
            track_id=track.track_id,
            bbox=track.bbox.as_int_tuple(),
            center=track.center,
            direction=track.direction,
            has_been_counted=track.has_been_counted,
            class_id=track.class_id,
            class_name=track.class_name,
            confidence=track.confidence,
        )

    @classmethod
    def from_tracked_vehicle(cls, tv) -> "TrackState":
        """
        Adapter: Convert from tracking.tracker.TrackedVehicle to TrackState.
        """
        return cls(
            track_id=tv.vehicle_id,
            bbox=tv.bbox,
            center=tv.center,
            direction=tv.direction,
            has_been_counted=tv.has_been_counted,
            class_id=getattr(tv, "class_id", None),
            class_name=getattr(tv, "class_name", None),
            confidence=getattr(tv, "confidence", 1.0),
        )

    @classmethod
    def from_domain_track_state(cls, ts) -> "TrackState":
        """
        Adapter: Convert from domain.models.TrackState to models.TrackState.
        """
        return cls(
            track_id=ts.track_id,
            bbox=ts.bbox,
            center=ts.center,
            direction=ts.direction,
            has_been_counted=ts.has_been_counted,
            class_id=getattr(ts, "class_id", None),
            class_name=getattr(ts, "class_name", None),
            confidence=getattr(ts, "confidence", 1.0),
        )


def tracks_from_tracked_vehicles(vehicles: List) -> List[Track]:
    """
    Adapter: Convert list of TrackedVehicle to list of Track.
    
    Args:
        vehicles: List of TrackedVehicle instances.
    """
    return [Track.from_tracked_vehicle(v) for v in vehicles]

