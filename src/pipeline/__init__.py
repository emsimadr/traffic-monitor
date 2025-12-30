"""
Pipeline module for the traffic monitoring system.

The pipeline orchestrates the full processing flow:
- Frame acquisition from observation sources
- Detection and tracking
- Counting and analytics
- Storage and web state updates
"""

from .engine import PipelineEngine, PipelineConfig

__all__ = ["PipelineEngine", "PipelineConfig"]

