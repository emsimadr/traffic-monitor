"""
CountEvent model for counting/crossing events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CountEvent:
    """
    A counting event emitted when a tracked object crosses the counting gate.
    
    Attributes:
        track_id: ID of the track that triggered the event.
        direction: Direction code (e.g., "A_TO_B", "B_TO_A").
        direction_label: Human-readable direction (e.g., "northbound").
        timestamp: Unix timestamp of the event.
        counting_mode: "line" or "gate".
        gate_sequence: Sequence of line crossings (e.g., "A_TO_B").
        line_a_cross_frame: Frame index when line A was crossed.
        line_b_cross_frame: Frame index when line B was crossed.
        track_age_frames: How many frames the track existed before counting.
        track_displacement_px: Total displacement in pixels.
    """
    track_id: int
    direction: str
    direction_label: str
    timestamp: float
    counting_mode: str = "gate"
    gate_sequence: Optional[str] = None
    line_a_cross_frame: Optional[int] = None
    line_b_cross_frame: Optional[int] = None
    track_age_frames: int = 0
    track_displacement_px: float = 0.0

    @classmethod
    def from_domain_count_event(cls, event) -> "CountEvent":
        """
        Adapter: Convert from domain.models.CountEvent to models.CountEvent.
        
        Args:
            event: A domain.models.CountEvent instance.
        """
        return cls(
            track_id=event.track_id,
            direction=event.direction,
            direction_label=event.direction_label,
            timestamp=event.timestamp,
            counting_mode=event.counting_mode,
            gate_sequence=event.gate_sequence,
            line_a_cross_frame=event.line_a_cross_frame,
            line_b_cross_frame=event.line_b_cross_frame,
            track_age_frames=event.track_age_frames,
            track_displacement_px=event.track_displacement_px,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "track_id": self.track_id,
            "direction": self.direction,
            "direction_label": self.direction_label,
            "timestamp": self.timestamp,
            "counting_mode": self.counting_mode,
            "gate_sequence": self.gate_sequence,
            "line_a_cross_frame": self.line_a_cross_frame,
            "line_b_cross_frame": self.line_b_cross_frame,
            "track_age_frames": self.track_age_frames,
            "track_displacement_px": self.track_displacement_px,
        }

