"""
Pipeline module for the traffic monitoring system.

The pipeline orchestrates the full processing flow:
- Frame acquisition from observation sources
- Detection and tracking
- Counting and analytics (via MeasureStage)
- Storage and web state updates
"""

from .engine import PipelineEngine, PipelineConfig, create_engine_from_config
from .stages.measure import MeasureStage, MeasureStageConfig, create_measure_stage

__all__ = [
    "PipelineEngine",
    "PipelineConfig",
    "create_engine_from_config",
    "MeasureStage",
    "MeasureStageConfig",
    "create_measure_stage",
]

