"""
Smoke tests for counting helpers and line crossing detection.
"""

import pytest
from analytics.counting import compute_counting_line


class TestComputeCountingLine:
    """Tests for compute_counting_line helper."""

    def test_horizontal_line_from_ratio(self):
        """A single float (0.5) should produce a horizontal line at 50% height."""
        line = compute_counting_line(0.5, frame_width=640, frame_height=480)
        
        assert len(line) == 2
        # Should be a horizontal line spanning full width at y=240
        assert line[0] == (0, 240)
        assert line[1] == (640, 240)

    def test_horizontal_line_at_top(self):
        """Ratio 0.0 should produce line at y=0."""
        line = compute_counting_line(0.0, frame_width=100, frame_height=100)
        
        assert line[0] == (0, 0)
        assert line[1] == (100, 0)

    def test_horizontal_line_at_bottom(self):
        """Ratio 1.0 should produce line at y=frame_height."""
        line = compute_counting_line(1.0, frame_width=100, frame_height=200)
        
        assert line[0] == (0, 200)
        assert line[1] == (100, 200)

    def test_diagonal_line_from_points(self):
        """Two-point config should produce diagonal/arbitrary line."""
        config = [[0.0, 0.0], [1.0, 1.0]]  # Top-left to bottom-right diagonal
        line = compute_counting_line(config, frame_width=100, frame_height=100)
        
        assert len(line) == 2
        assert line[0] == (0, 0)
        assert line[1] == (100, 100)

    def test_arbitrary_line(self):
        """Arbitrary line with non-trivial coordinates."""
        config = [[0.2, 0.3], [0.8, 0.7]]
        line = compute_counting_line(config, frame_width=1000, frame_height=500)
        
        assert len(line) == 2
        assert line[0] == (200, 150)  # 0.2*1000, 0.3*500
        assert line[1] == (800, 350)  # 0.8*1000, 0.7*500

    def test_integer_ratio_treated_as_float(self):
        """Integer ratio (like 0) should work same as float."""
        line = compute_counting_line(0, frame_width=640, frame_height=480)
        
        assert line[0] == (0, 0)
        assert line[1] == (640, 0)


class TestLineCrossing:
    """Tests for line crossing detection helpers from counter module."""

    def test_side_of_line_positive(self):
        """Point on positive side of line (cross product > 0)."""
        from analytics.counter import _side_of_line
        
        # Line from (0,0) to (10,0) (horizontal going right)
        # Point (5, 5) is below the line (positive y in screen coords)
        result = _side_of_line((5, 5), (0, 0), (10, 0))
        assert result > 0  # Below line = positive cross product

    def test_side_of_line_negative(self):
        """Point on negative side of line (cross product < 0)."""
        from analytics.counter import _side_of_line
        
        # Line from (0,0) to (10,0) (horizontal going right)
        # Point (5, -5) is above the line (negative y in screen coords)
        result = _side_of_line((5, -5), (0, 0), (10, 0))
        assert result < 0  # Above line = negative cross product

    def test_side_of_line_on_line(self):
        """Point exactly on the line."""
        from analytics.counter import _side_of_line
        
        # Point (5, 0) is on the line from (0,0) to (10,0)
        result = _side_of_line((5, 0), (0, 0), (10, 0))
        assert result == 0

    def test_segments_intersect_crossing(self):
        """Two segments that clearly cross."""
        from analytics.counter import _segments_intersect
        
        # Segment from (0,0) to (10,10) crosses segment from (0,10) to (10,0)
        assert _segments_intersect((0, 0), (10, 10), (0, 10), (10, 0)) is True

    def test_segments_intersect_no_crossing(self):
        """Two segments that don't cross."""
        from analytics.counter import _segments_intersect
        
        # Parallel horizontal segments
        assert _segments_intersect((0, 0), (10, 0), (0, 10), (10, 10)) is False

    def test_segments_intersect_endpoint_touch(self):
        """Segments touching at endpoint."""
        from analytics.counter import _segments_intersect
        
        # Segments sharing endpoint - should count as crossing
        assert _segments_intersect((0, 0), (5, 5), (5, 5), (10, 0)) is True

