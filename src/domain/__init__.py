"""
Domain-level models and contracts.

Note: The canonical model definitions are in src/models/.
This module re-exports them for backward compatibility.
"""

from models.count_event import CountEvent
from models.detection import Detection
from models.track import TrackState

__all__ = ["Detection", "TrackState", "CountEvent"]
