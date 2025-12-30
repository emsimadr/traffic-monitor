"""
Measure stage for counting tracked objects.

This stage uses a Counter to produce CountEvents from tracks,
then persists events to storage exactly as before.

Supports two counting modes:
- "line": Single line crossing (LineCounter)
- "gate": Two-line gate sequence (GateCounter)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from models.count_event import CountEvent
from algorithms.counting.base import Counter
from algorithms.counting.line import LineCounter, LineCounterConfig, create_line_counter_from_config
from algorithms.counting.gate import GateCounter, GateCounterConfig, create_gate_counter_from_config


@dataclass
class MeasureStageConfig:
    """
    Configuration for the measure stage.
    
    Attributes:
        counting_config: Raw counting config from YAML.
        persist_events: Whether to persist events to database.
    """
    counting_config: Dict[str, Any] = field(default_factory=dict)
    persist_events: bool = True


class MeasureStage:
    """
    Pipeline stage that counts tracked objects crossing lines.
    
    This stage:
    - Creates and manages a Counter instance
    - Processes tracks each frame to detect crossings
    - Persists count events to the database
    - Does NOT modify track objects
    
    Example:
        stage = MeasureStage(config, db)
        stage.ensure_counter(frame_width, frame_height)
        
        # Each frame:
        events = stage.process(tracks, frame_idx)
    """

    def __init__(
        self,
        config: MeasureStageConfig,
        db: Any = None,
        on_event: Optional[Callable[[CountEvent], None]] = None,
    ):
        """
        Initialize the measure stage.
        
        Args:
            config: Stage configuration.
            db: Database instance for persisting events.
            on_event: Optional callback for each count event.
        """
        self._config = config
        self._db = db
        self._on_event = on_event
        self._counter: Optional[Counter] = None
        self._frame_size: Optional[Tuple[int, int]] = None

    @property
    def counter(self) -> Optional[Counter]:
        """Get the current counter instance."""
        return self._counter

    @property
    def is_initialized(self) -> bool:
        """Check if the counter has been initialized."""
        return self._counter is not None

    def ensure_counter(self, frame_width: int, frame_height: int) -> None:
        """
        Ensure the counter is initialized for the given frame size.
        
        Selects counter based on config mode:
        - "gate": GateCounter (two-line gate sequence)
        - "line" or default: LineCounter (single line crossing)
        
        Args:
            frame_width: Frame width in pixels.
            frame_height: Frame height in pixels.
        """
        if self._counter is not None:
            return
        
        self._frame_size = (frame_width, frame_height)
        mode = self._config.counting_config.get("mode", "line")
        
        if mode == "gate":
            self._counter = create_gate_counter_from_config(
                self._config.counting_config,
                frame_width,
                frame_height,
            )
            logging.info(f"MeasureStage initialized GateCounter (mode=gate)")
        else:
            self._counter = create_line_counter_from_config(
                self._config.counting_config,
                frame_width,
                frame_height,
            )
            logging.info(f"MeasureStage initialized LineCounter (mode={mode})")
        
        logging.debug(f"Counting lines: {len(self._counter.get_lines())}")

    def process(self, tracks: List[Any], frame_idx: int) -> List[CountEvent]:
        """
        Process tracks and produce count events.
        
        Args:
            tracks: List of track objects from the tracker.
            frame_idx: Current frame index.
            
        Returns:
            List of CountEvent objects for this frame.
        """
        if self._counter is None:
            return []
        
        # Run counter (does not modify tracks)
        events = self._counter.process(tracks, frame_idx)
        
        # Persist and notify
        for event in events:
            self._persist_event(event)
            if self._on_event:
                try:
                    self._on_event(event)
                except Exception as e:
                    logging.warning(f"Event callback error: {e}")
        
        return events

    def _persist_event(self, event: CountEvent) -> None:
        """Persist a count event to the database."""
        if not self._config.persist_events:
            return
        
        if self._db is None:
            return
        
        try:
            self._db.add_count_event(event)
        except Exception as e:
            logging.error(f"Failed to persist count event: {e}")

    def get_lines(self) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """Get counting lines for visualization."""
        if self._counter is None:
            return []
        return self._counter.get_lines()

    def get_line_a(self) -> Optional[List[Tuple[int, int]]]:
        """Get line A for visualization (compatibility with old API)."""
        if self._counter is None:
            return None
        if isinstance(self._counter, GateCounter):
            return self._counter.line_a if self._counter.line_a else None
        if isinstance(self._counter, LineCounter):
            return self._counter.line if self._counter.line else None
        return None

    def get_line_b(self) -> Optional[List[Tuple[int, int]]]:
        """Get line B for visualization (compatibility with old API)."""
        if self._counter is None:
            return None
        if isinstance(self._counter, GateCounter):
            return self._counter.line_b if self._counter.line_b else None
        # LineCounter has only one line
        return None

    def get_gate_lines(self) -> Tuple[Optional[List[Tuple[int, int]]], Optional[List[Tuple[int, int]]]]:
        """
        Get gate lines for visualization.
        
        Returns:
            Tuple of (line_a, line_b) for compatibility with existing code.
            For LineCounter, returns (line, None).
        """
        return self.get_line_a(), self.get_line_b()

    def is_counted(self, track_id: int) -> bool:
        """Check if a track has been counted."""
        if self._counter is None:
            return False
        return self._counter.is_counted(track_id)

    def reset(self) -> None:
        """Reset the counter state."""
        if self._counter is not None:
            self._counter.reset()


def create_measure_stage(
    counting_cfg: Dict[str, Any],
    db: Any = None,
    persist: bool = True,
) -> MeasureStage:
    """
    Factory function to create a MeasureStage from config.
    
    Args:
        counting_cfg: Counting configuration from YAML.
        db: Database instance.
        persist: Whether to persist events.
    """
    config = MeasureStageConfig(
        counting_config=counting_cfg,
        persist_events=persist,
    )
    return MeasureStage(config, db=db)

