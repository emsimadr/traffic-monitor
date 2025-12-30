"""
Counting algorithms for traffic monitoring.

This module provides counting strategies that process tracks and produce count events.
The tracking layer remains independent - counters do not modify track state.
"""

from .base import Counter, CounterConfig
from .line import LineCounter, LineCounterConfig

__all__ = [
    "Counter",
    "CounterConfig",
    "LineCounter",
    "LineCounterConfig",
]

