"""
Observation layer for pluggable video/image sources.

This layer abstracts the source of frames (camera, video file, remote stream)
from the processing pipeline. Each source implements the ObservationSource
interface and returns FrameData objects.

Available sources:
- OpenCVSource: USB cameras, RTSP streams, video files (cross-platform)
- Picamera2Source: Raspberry Pi CSI cameras (Pi only)
"""

from .base import ObservationSource, ObservationConfig
from .opencv_source import OpenCVSource, OpenCVSourceConfig
from .rtsp_utils import inject_rtsp_credentials

# Picamera2 is optional (only works on Raspberry Pi)
try:
    from .picamera2_source import Picamera2Source, Picamera2SourceConfig
    _HAS_PICAMERA2 = True
except ImportError:
    _HAS_PICAMERA2 = False
    Picamera2Source = None  # type: ignore
    Picamera2SourceConfig = None  # type: ignore


def create_source_from_config(camera_cfg: dict, source_id: str = "camera") -> ObservationSource:
    """
    Factory function to create an observation source from config.
    
    Handles credential injection for RTSP streams automatically.
    
    Args:
        camera_cfg: Camera configuration dict.
        source_id: Identifier for this source.
        
    Returns:
        Configured ObservationSource instance.
    """
    # Inject credentials if secrets_file is specified (modifies camera_cfg in place)
    inject_rtsp_credentials(camera_cfg)
    
    backend = camera_cfg.get("backend", "opencv")
    
    if backend == "picamera2":
        if not _HAS_PICAMERA2:
            raise ImportError(
                "Picamera2 backend requested but not available. "
                "Install with `sudo apt install -y python3-picamera2` or use backend 'opencv'."
            )
        config = Picamera2SourceConfig.from_camera_config(camera_cfg, source_id)
        return Picamera2Source(config)
    else:
        config = OpenCVSourceConfig.from_camera_config(camera_cfg, source_id)
        return OpenCVSource(config)


__all__ = [
    "ObservationSource",
    "ObservationConfig",
    "OpenCVSource",
    "OpenCVSourceConfig",
    "Picamera2Source",
    "Picamera2SourceConfig",
    "create_source_from_config",
]

