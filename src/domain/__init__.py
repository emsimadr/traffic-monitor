"""
Domain-level models and contracts for detections, tracking, and counting events.
Keeping these simple and typed helps enforce boundaries between components.
"""

from .models import Detection, TrackState, CountEvent  # noqa: F401


