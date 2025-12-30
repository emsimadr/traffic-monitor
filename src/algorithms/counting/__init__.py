"""
Counting algorithms for traffic monitoring.

This module provides counting strategies that process tracks and produce count events.
The tracking layer remains independent - counters do not modify track state.

Available counters:
- LineCounter: Single-line counting (counts on any crossing)
- GateCounter: Two-line gate counting (A->B or B->A sequences)
"""

from .base import Counter, CounterConfig
from .line import LineCounter, LineCounterConfig, create_line_counter_from_config
from .gate import GateCounter, GateCounterConfig, create_gate_counter_from_config

__all__ = [
    "Counter",
    "CounterConfig",
    "LineCounter",
    "LineCounterConfig",
    "create_line_counter_from_config",
    "GateCounter",
    "GateCounterConfig",
    "create_gate_counter_from_config",
]

