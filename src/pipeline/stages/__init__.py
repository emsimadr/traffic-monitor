"""
Pipeline stages for the traffic monitoring system.

Each stage handles a specific part of the processing pipeline:
- detect: Object detection
- track: Object tracking
- measure: Counting/measurement
- annotate: Frame annotation
"""

from .measure import MeasureStage, MeasureStageConfig

__all__ = ["MeasureStage", "MeasureStageConfig"]

