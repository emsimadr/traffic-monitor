from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Detection:
    """Detection result from a detector backend."""

    bbox: Tuple[int, int, int, int]
    score: Optional[float] = None
    class_id: Optional[int] = None
    timestamp: Optional[float] = None


@dataclass(frozen=True)
class TrackState:
    """Snapshot of a tracked object."""

    track_id: int
    bbox: Tuple[int, int, int, int]
    center: Tuple[float, float]
    direction: Optional[str]
    has_been_counted: bool


@dataclass(frozen=True)
class CountEvent:
    """A counting event emitted by a counter strategy."""

    track_id: int
    direction: str  # direction code (e.g., A_TO_B, B_TO_A)
    direction_label: str
    timestamp: float
    counting_mode: str  # "line" | "gate"
    gate_sequence: Optional[str]
    line_a_cross_frame: Optional[int]
    line_b_cross_frame: Optional[int]
    track_age_frames: int
    track_displacement_px: float


