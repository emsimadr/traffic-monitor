"""
Smoke tests for configuration loading and validation.
"""

import os
import pytest

from main import load_config, validate_config


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_valid_config_passes(self, valid_config):
        """A complete valid config passes validation."""
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is True
        assert error is None

    def test_missing_camera_section(self, valid_config):
        """Missing camera section fails validation."""
        del valid_config["camera"]
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "camera" in error.lower()

    def test_missing_detection_section(self, valid_config):
        """Missing detection section fails validation."""
        del valid_config["detection"]
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "detection" in error.lower()

    def test_missing_storage_section(self, valid_config):
        """Missing storage section fails validation."""
        del valid_config["storage"]
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "storage" in error.lower()

    def test_missing_log_level(self, valid_config):
        """Missing log_level fails validation."""
        del valid_config["log_level"]
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "log_level" in error.lower()

    def test_missing_log_path(self, valid_config):
        """Missing log_path fails validation."""
        del valid_config["log_path"]
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "log_path" in error.lower()

    def test_invalid_device_id_type(self, valid_config):
        """device_id with invalid type fails."""
        valid_config["camera"]["device_id"] = [1, 2, 3]
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "device_id" in error.lower()

    def test_negative_device_id(self, valid_config):
        """Negative integer device_id fails."""
        valid_config["camera"]["device_id"] = -1
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "device_id" in error.lower()

    def test_string_device_id_valid(self, valid_config):
        """String device_id (RTSP URL) is valid."""
        valid_config["camera"]["device_id"] = "rtsp://192.168.1.1/stream"
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is True

    def test_invalid_resolution_format(self, valid_config):
        """Invalid resolution format fails."""
        valid_config["camera"]["resolution"] = 1920  # Should be list
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "resolution" in error.lower()

    def test_invalid_resolution_length(self, valid_config):
        """Resolution with wrong length fails."""
        valid_config["camera"]["resolution"] = [1920]  # Should be [width, height]
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "resolution" in error.lower()

    def test_invalid_fps(self, valid_config):
        """Non-positive fps fails."""
        valid_config["camera"]["fps"] = 0
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "fps" in error.lower()

    def test_invalid_camera_backend(self, valid_config):
        """Unknown camera backend fails."""
        valid_config["camera"]["backend"] = "unknown_backend"
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "backend" in error.lower()

    def test_picamera2_backend_valid(self, valid_config):
        """picamera2 backend is valid."""
        valid_config["camera"]["backend"] = "picamera2"
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is True

    def test_invalid_detection_backend(self, valid_config):
        """Unknown detection backend fails."""
        valid_config["detection"]["backend"] = "magic"
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "backend" in error.lower()

    def test_yolo_backend_requires_model(self, valid_config):
        """YOLO backend without model fails."""
        valid_config["detection"]["backend"] = "yolo"
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "model" in error.lower()

    def test_yolo_backend_with_model(self, valid_config):
        """YOLO backend with model passes."""
        valid_config["detection"]["backend"] = "yolo"
        valid_config["detection"]["yolo"] = {"model": "yolov8n.pt"}
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is True

    def test_invalid_log_level(self, valid_config):
        """Invalid log level fails."""
        valid_config["log_level"] = "VERBOSE"  # Not a valid level
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "log_level" in error.lower()

    def test_valid_tracking_config(self, valid_config):
        """Valid tracking config passes."""
        valid_config["tracking"] = {
            "max_frames_since_seen": 15,
            "min_trajectory_length": 5,
            "iou_threshold": 0.4,
        }
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is True

    def test_invalid_tracking_iou(self, valid_config):
        """Invalid tracking.iou_threshold fails."""
        valid_config["tracking"] = {"iou_threshold": 1.5}  # Should be <= 1
        
        is_valid, error = validate_config(valid_config)
        
        assert is_valid is False
        assert "iou_threshold" in error.lower()


class TestLoadConfig:
    """Tests for load_config function."""

    def test_loads_default_yaml(self, temp_config_dir):
        """Config loads from default.yaml when only it exists."""
        config_path = str(temp_config_dir / "config.yaml")
        
        # Don't create config.yaml, only default.yaml exists
        config = load_config(config_path)
        
        assert config["camera"]["backend"] == "opencv"
        assert config["camera"]["device_id"] == 0
        assert config["camera"]["resolution"] == [640, 480]

    def test_local_overrides_merge(self, temp_config_dir):
        """Local config.yaml overrides default.yaml."""
        # Create config.yaml with override
        config_yaml = temp_config_dir / "config.yaml"
        config_yaml.write_text("""
camera:
  resolution: [1920, 1080]
  fps: 60
""")
        
        config = load_config(str(config_yaml))
        
        # Overridden values
        assert config["camera"]["resolution"] == [1920, 1080]
        assert config["camera"]["fps"] == 60
        
        # Original values preserved
        assert config["camera"]["backend"] == "opencv"
        assert config["camera"]["device_id"] == 0

    def test_deep_merge_preserves_nested(self, temp_config_dir):
        """Deep merge preserves nested keys not overridden."""
        config_yaml = temp_config_dir / "config.yaml"
        config_yaml.write_text("""
detection:
  backend: "yolo"
  yolo:
    model: "yolov8n.pt"
""")
        
        config = load_config(str(config_yaml))
        
        # New values
        assert config["detection"]["backend"] == "yolo"
        assert config["detection"]["yolo"]["model"] == "yolov8n.pt"
        
        # Original detection values preserved
        assert config["detection"]["min_contour_area"] == 1000

