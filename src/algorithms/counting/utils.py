"""
Counting utilities.

Shared helpers for line/gate counting algorithms.
"""

from __future__ import annotations

from typing import List, Tuple, Union


CountingLineConfig = Union[float, int, List[List[float]]]


def compute_counting_line(
    counting_config: CountingLineConfig,
    frame_width: int,
    frame_height: int
) -> List[Tuple[int, int]]:
    """
    Convert config-based line definition into pixel coordinates.

    Args:
        counting_config: Either a number (Y ratio for horizontal line)
                         or [[x1,y1],[x2,y2]] ratios for arbitrary line.
        frame_width: Width of the frame in pixels.
        frame_height: Height of the frame in pixels.

    Returns:
        List of two (x, y) tuples representing line endpoints in pixels.
    """
    if isinstance(counting_config, (int, float)):
        line_y = int(frame_height * float(counting_config))
        return [(0, line_y), (frame_width, line_y)]

    # diagonal / arbitrary line in ratios
    p1 = (int(counting_config[0][0] * frame_width), int(counting_config[0][1] * frame_height))
    p2 = (int(counting_config[1][0] * frame_width), int(counting_config[1][1] * frame_height))
    return [p1, p2]

