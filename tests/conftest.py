"""
Pytest configuration and shared fixtures.
"""

import os
import sys
import tempfile

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory with default.yaml."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    default_yaml = config_dir / "default.yaml"
    default_yaml.write_text("""
camera:
  backend: "opencv"
  device_id: 0
  resolution: [640, 480]
  fps: 30

detection:
  backend: "bgsub"
  min_contour_area: 1000
  detect_shadows: true

storage:
  local_database_path: "data/test.sqlite"
  retention_days: 7
  use_cloud_storage: false

log_path: "logs/test.log"
log_level: "INFO"
""")
    
    return config_dir


@pytest.fixture
def valid_config():
    """Return a valid configuration dictionary."""
    return {
        "camera": {
            "backend": "opencv",
            "device_id": 0,
            "resolution": [1280, 720],
            "fps": 30,
        },
        "detection": {
            "backend": "bgsub",
            "min_contour_area": 1000,
            "detect_shadows": True,
        },
        "storage": {
            "local_database_path": "data/test.sqlite",
            "retention_days": 30,
            "use_cloud_storage": False,
        },
        "log_path": "logs/test.log",
        "log_level": "INFO",
    }
