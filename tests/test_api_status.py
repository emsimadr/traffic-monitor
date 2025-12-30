"""
Tests for GET /api/status compact status endpoint.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from web.routes.api import _compute_warnings, _get_today_start_timestamp


class TestComputeWarnings:
    """Tests for warning computation logic."""
    
    def test_no_warnings_when_healthy(self):
        """No warnings when all metrics are healthy."""
        warnings = _compute_warnings(
            last_frame_age_s=0.5,  # Recent frame
            disk_free_pct=50.0,    # Plenty of disk
            cpu_temp_c=45.0,       # Cool CPU
        )
        assert warnings == []
    
    def test_camera_stale_warning(self):
        """camera_stale when last_frame_age > 2s but <= 10s."""
        warnings = _compute_warnings(
            last_frame_age_s=5.0,
            disk_free_pct=50.0,
            cpu_temp_c=45.0,
        )
        assert "camera_stale" in warnings
        assert "camera_offline" not in warnings
    
    def test_camera_offline_warning(self):
        """camera_offline when last_frame_age > 10s."""
        warnings = _compute_warnings(
            last_frame_age_s=15.0,
            disk_free_pct=50.0,
            cpu_temp_c=45.0,
        )
        assert "camera_offline" in warnings
        assert "camera_stale" not in warnings
    
    def test_camera_offline_when_no_timestamp(self):
        """camera_offline when last_frame_age is None."""
        warnings = _compute_warnings(
            last_frame_age_s=None,
            disk_free_pct=50.0,
            cpu_temp_c=45.0,
        )
        assert "camera_offline" in warnings
    
    def test_disk_low_warning(self):
        """disk_low when disk_free_pct < 10."""
        warnings = _compute_warnings(
            last_frame_age_s=0.5,
            disk_free_pct=5.0,
            cpu_temp_c=45.0,
        )
        assert "disk_low" in warnings
    
    def test_disk_low_threshold_exact(self):
        """disk_low not triggered at exactly 10%."""
        warnings = _compute_warnings(
            last_frame_age_s=0.5,
            disk_free_pct=10.0,
            cpu_temp_c=45.0,
        )
        assert "disk_low" not in warnings
    
    def test_temp_high_warning(self):
        """temp_high when cpu_temp_c > 80."""
        warnings = _compute_warnings(
            last_frame_age_s=0.5,
            disk_free_pct=50.0,
            cpu_temp_c=85.0,
        )
        assert "temp_high" in warnings
    
    def test_temp_high_threshold_exact(self):
        """temp_high not triggered at exactly 80°C."""
        warnings = _compute_warnings(
            last_frame_age_s=0.5,
            disk_free_pct=50.0,
            cpu_temp_c=80.0,
        )
        assert "temp_high" not in warnings
    
    def test_multiple_warnings(self):
        """Multiple warnings can be active simultaneously."""
        warnings = _compute_warnings(
            last_frame_age_s=15.0,  # camera_offline
            disk_free_pct=5.0,      # disk_low
            cpu_temp_c=90.0,        # temp_high
        )
        assert "camera_offline" in warnings
        assert "disk_low" in warnings
        assert "temp_high" in warnings
        assert len(warnings) == 3
    
    def test_none_values_safe(self):
        """None values for optional metrics don't cause errors."""
        warnings = _compute_warnings(
            last_frame_age_s=0.5,
            disk_free_pct=None,
            cpu_temp_c=None,
        )
        assert "disk_low" not in warnings
        assert "temp_high" not in warnings


class TestGetTodayStartTimestamp:
    """Tests for today start timestamp helper."""
    
    def test_returns_float(self):
        """Returns a float timestamp."""
        ts = _get_today_start_timestamp()
        assert isinstance(ts, float)
    
    def test_is_in_past(self):
        """Today start is in the past."""
        ts = _get_today_start_timestamp()
        assert ts <= time.time()
    
    def test_is_within_24_hours(self):
        """Today start is within the last 24 hours."""
        ts = _get_today_start_timestamp()
        assert time.time() - ts < 86400


class TestCompactStatusEndpoint:
    """Integration tests for the /api/status endpoint."""
    
    @pytest.fixture
    def mock_state(self):
        """Create a mock state object."""
        mock = MagicMock()
        mock.get_system_stats_copy.return_value = {
            "fps": 25.0,
            "last_frame_ts": time.time() - 0.5,  # Recent frame
            "start_time": time.time() - 3600,
        }
        mock.get_config_copy.return_value = {
            "counting": {
                "direction_labels": {
                    "a_to_b": "northbound",
                    "b_to_a": "southbound",
                }
            }
        }
        mock.database = MagicMock()
        mock.database.get_count_total.return_value = 42
        mock.database.get_counts_by_direction_code.return_value = {
            "A_TO_B": 25,
            "B_TO_A": 17,
        }
        return mock
    
    def test_response_has_required_keys(self, mock_state):
        """Response includes all required keys."""
        with patch("web.routes.api.state", mock_state):
            with patch("web.routes.api.HealthService") as mock_health:
                mock_health.disk_usage.return_value = {"pct_free": 50.0}
                mock_health.read_cpu_temp_c.return_value = 45.0
                
                from web.routes.api import compact_status
                response = compact_status()
        
        # Check all required keys
        assert hasattr(response, "running")
        assert hasattr(response, "last_frame_age_s")
        assert hasattr(response, "fps_capture")
        assert hasattr(response, "fps_infer")
        assert hasattr(response, "infer_latency_ms_p50")
        assert hasattr(response, "infer_latency_ms_p95")
        assert hasattr(response, "counts_today_total")
        assert hasattr(response, "counts_by_direction_code")
        assert hasattr(response, "direction_labels")
        assert hasattr(response, "cpu_temp_c")
        assert hasattr(response, "disk_free_pct")
        assert hasattr(response, "warnings")
    
    def test_running_true_when_recent_frame(self, mock_state):
        """running=True when camera has recent frames."""
        with patch("web.routes.api.state", mock_state):
            with patch("web.routes.api.HealthService") as mock_health:
                mock_health.disk_usage.return_value = {"pct_free": 50.0}
                mock_health.read_cpu_temp_c.return_value = 45.0
                
                from web.routes.api import compact_status
                response = compact_status()
        
        assert response.running is True
        assert "camera_offline" not in response.warnings
    
    def test_running_false_when_camera_offline(self, mock_state):
        """running=False when camera is offline."""
        mock_state.get_system_stats_copy.return_value = {
            "fps": 0,
            "last_frame_ts": time.time() - 30,  # Stale frame
        }
        
        with patch("web.routes.api.state", mock_state):
            with patch("web.routes.api.HealthService") as mock_health:
                mock_health.disk_usage.return_value = {"pct_free": 50.0}
                mock_health.read_cpu_temp_c.return_value = 45.0
                
                from web.routes.api import compact_status
                response = compact_status()
        
        assert response.running is False
        assert "camera_offline" in response.warnings
    
    def test_counts_from_database(self, mock_state):
        """Counts come from database."""
        with patch("web.routes.api.state", mock_state):
            with patch("web.routes.api.HealthService") as mock_health:
                mock_health.disk_usage.return_value = {"pct_free": 50.0}
                mock_health.read_cpu_temp_c.return_value = 45.0
                
                from web.routes.api import compact_status
                response = compact_status()
        
        assert response.counts_today_total == 42
        assert response.counts_by_direction_code == {"A_TO_B": 25, "B_TO_A": 17}
    
    def test_direction_labels_from_config(self, mock_state):
        """Direction labels come from config."""
        with patch("web.routes.api.state", mock_state):
            with patch("web.routes.api.HealthService") as mock_health:
                mock_health.disk_usage.return_value = {"pct_free": 50.0}
                mock_health.read_cpu_temp_c.return_value = 45.0
                
                from web.routes.api import compact_status
                response = compact_status()
        
        assert response.direction_labels["A_TO_B"] == "northbound"
        assert response.direction_labels["B_TO_A"] == "southbound"
    
    def test_warnings_triggered(self, mock_state):
        """Warnings are correctly triggered."""
        mock_state.get_system_stats_copy.return_value = {
            "fps": 25.0,
            "last_frame_ts": time.time() - 5,  # Stale
        }
        
        with patch("web.routes.api.state", mock_state):
            with patch("web.routes.api.HealthService") as mock_health:
                mock_health.disk_usage.return_value = {"pct_free": 5.0}  # Low disk
                mock_health.read_cpu_temp_c.return_value = 85.0  # High temp
                
                from web.routes.api import compact_status
                response = compact_status()
        
        assert "camera_stale" in response.warnings
        assert "disk_low" in response.warnings
        assert "temp_high" in response.warnings
    
    def test_handles_no_database(self, mock_state):
        """Handles case when database is None."""
        mock_state.database = None
        
        with patch("web.routes.api.state", mock_state):
            with patch("web.routes.api.HealthService") as mock_health:
                mock_health.disk_usage.return_value = {"pct_free": 50.0}
                mock_health.read_cpu_temp_c.return_value = 45.0
                
                from web.routes.api import compact_status
                response = compact_status()
        
        assert response.counts_today_total == 0
        assert response.counts_by_direction_code == {}
    
    def test_handles_database_error(self, mock_state):
        """Handles database errors gracefully."""
        mock_state.database.get_count_total.side_effect = Exception("DB error")
        
        with patch("web.routes.api.state", mock_state):
            with patch("web.routes.api.HealthService") as mock_health:
                mock_health.disk_usage.return_value = {"pct_free": 50.0}
                mock_health.read_cpu_temp_c.return_value = 45.0
                
                from web.routes.api import compact_status
                response = compact_status()
        
        # Should not raise, just return 0 counts
        assert response.counts_today_total == 0

