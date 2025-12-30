"""
Counter interface for counting algorithms.

All counting strategies (gate, line, etc.) implement this interface.
They process tracks and produce CountEvents with standardized direction codes
(A_TO_B, B_TO_A) regardless of the underlying algorithm.

This separation allows tracking and counting to evolve independently.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

from models.count_event import CountEvent


# Standard direction codes used in DB and API responses
DIRECTION_A_TO_B = "A_TO_B"
DIRECTION_B_TO_A = "B_TO_A"


@dataclass
class CounterConfig:
    """
    Base configuration for counting algorithms.
    
    All counters use the same direction code format (A_TO_B, B_TO_A)
    for database and API consistency.
    
    Attributes:
        direction_labels: Mapping of direction codes (a_to_b, b_to_a) to display labels.
        min_trajectory_length: Minimum trajectory points needed for counting.
    """
    direction_labels: Dict[str, str] = field(default_factory=lambda: {
        "a_to_b": "northbound",
        "b_to_a": "southbound",
    })
    min_trajectory_length: int = 2


class Counter(ABC):
    """
    Abstract base class for counting algorithms.
    
    A counter processes a list of tracks and produces CountEvents.
    Counters maintain their own internal state to track which objects
    have been counted, but they do NOT modify the track objects themselves.
    
    All counters MUST produce CountEvents with direction codes A_TO_B or B_TO_A
    for database and API consistency.
    
    This design allows:
    - Tracking layer to remain pure (tracks only)
    - Multiple counters to run on the same tracks
    - Easy testing and swapping of counting strategies
    - Consistent direction codes regardless of strategy
    """

    def __init__(self, config: CounterConfig):
        self._config = config
        self._counted_track_ids: Set[int] = set()

    @property
    def direction_labels(self) -> Dict[str, str]:
        """Get direction label mapping."""
        return self._config.direction_labels

    def is_counted(self, track_id: int) -> bool:
        """Check if a track has already been counted."""
        return track_id in self._counted_track_ids

    def mark_counted(self, track_id: int) -> None:
        """Mark a track as counted (internal state only)."""
        self._counted_track_ids.add(track_id)

    def get_counted_ids(self) -> Set[int]:
        """Get set of all counted track IDs."""
        return self._counted_track_ids.copy()

    def reset(self) -> None:
        """Reset counter state (clear counted IDs)."""
        self._counted_track_ids.clear()

    @abstractmethod
    def process(self, tracks: List[Any], frame_idx: int) -> List[CountEvent]:
        """
        Process tracks and produce count events.
        
        This method should NOT modify track objects. It should only:
        - Read track state (bbox, center, trajectory)
        - Update internal counter state
        - Return CountEvent objects for newly counted tracks
        
        CountEvents MUST have direction set to DIRECTION_A_TO_B or DIRECTION_B_TO_A.
        
        Args:
            tracks: List of track objects with trajectory information.
            frame_idx: Current frame index for timing information.
            
        Returns:
            List of CountEvent objects for tracks that crossed in this frame.
        """
        pass

    @abstractmethod
    def get_lines(self) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """
        Get the counting lines for visualization.
        
        Returns:
            List of line segments as ((x1,y1), (x2,y2)) tuples.
        """
        pass
