"""
Tests for observation layer.
"""

import time
import pytest
import numpy as np

from observation.base import ObservationSource, ObservationConfig
from observation.opencv_source import OpenCVSource, OpenCVSourceConfig
from models.frame import FrameData


class MockSource(ObservationSource):
    """Mock observation source for testing."""
    
    def __init__(self, config: ObservationConfig, frames: list = None):
        super().__init__(config)
        self._frames = frames or []
        self._pos = 0
    
    def open(self) -> None:
        self._is_open = True
        self._pos = 0
        self._frame_index = 0
    
    def read(self) -> FrameData | None:
        if not self._is_open or self._pos >= len(self._frames):
            return None
        
        frame = self._frames[self._pos]
        self._pos += 1
        self._frame_index += 1
        
        return FrameData(
            frame=frame,
            width=frame.shape[1],
            height=frame.shape[0],
            timestamp=time.time(),
            frame_index=self._frame_index,
            source=self.source_id,
        )
    
    def close(self) -> None:
        self._is_open = False


class TestObservationConfig:
    def test_default_config(self):
        config = ObservationConfig()
        assert config.source_id == "default"
        assert config.resolution is None
        assert config.fps is None

    def test_custom_config(self):
        config = ObservationConfig(
            source_id="cam-01",
            resolution=(1920, 1080),
            fps=30,
            metadata={"location": "entrance"},
        )
        assert config.source_id == "cam-01"
        assert config.resolution == (1920, 1080)
        assert config.metadata["location"] == "entrance"


class TestOpenCVSourceConfig:
    def test_from_camera_config(self):
        camera_cfg = {
            "device_id": "rtsp://192.168.1.100/stream",
            "resolution": [1280, 720],
            "fps": 30,
            "swap_rb": True,
            "rotate": 90,
        }
        config = OpenCVSourceConfig.from_camera_config(camera_cfg, source_id="traffic-cam")
        
        assert config.source_id == "traffic-cam"
        assert config.device_id == "rtsp://192.168.1.100/stream"
        assert config.resolution == (1280, 720)
        assert config.fps == 30
        assert config.swap_rb is True
        assert config.rotate == 90


class TestMockSource:
    def test_source_lifecycle(self):
        config = ObservationConfig(source_id="test")
        frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(3)]
        source = MockSource(config, frames)
        
        assert not source.is_open
        source.open()
        assert source.is_open
        assert source.frame_index == 0
        
        fd = source.read()
        assert fd is not None
        assert fd.source == "test"
        assert fd.frame_index == 1
        assert source.frame_index == 1
        
        source.close()
        assert not source.is_open

    def test_context_manager(self):
        config = ObservationConfig(source_id="ctx-test")
        frames = [np.zeros((50, 50, 3), dtype=np.uint8) for _ in range(2)]
        
        with MockSource(config, frames) as source:
            assert source.is_open
            count = sum(1 for _ in source)
            assert count == 2
        
        assert not source.is_open

    def test_iteration(self):
        config = ObservationConfig(source_id="iter-test")
        frames = [np.ones((10, 10, 3), dtype=np.uint8) * i for i in range(5)]
        
        with MockSource(config, frames) as source:
            collected = list(source)
        
        assert len(collected) == 5
        for i, fd in enumerate(collected):
            assert fd.frame_index == i + 1
            assert fd.source == "iter-test"

    def test_empty_source(self):
        config = ObservationConfig()
        with MockSource(config, []) as source:
            result = source.read()
            assert result is None

    def test_iteration_requires_open(self):
        config = ObservationConfig()
        source = MockSource(config, [])
        
        with pytest.raises(RuntimeError, match="must be open"):
            list(source)


class TestOpenCVSource:
    def test_is_rtsp_detection(self):
        rtsp_config = OpenCVSourceConfig(device_id="rtsp://192.168.1.1/stream")
        source = OpenCVSource(rtsp_config)
        assert source.is_rtsp is True
        assert source.is_file is False

    def test_usb_camera_detection(self):
        usb_config = OpenCVSourceConfig(device_id=0)
        source = OpenCVSource(usb_config)
        assert source.is_rtsp is False
        assert source.is_file is False

    def test_source_id_property(self):
        config = OpenCVSourceConfig(source_id="my-camera", device_id=0)
        source = OpenCVSource(config)
        assert source.source_id == "my-camera"

    def test_frame_data_structure(self):
        """Test that FrameData has expected fields."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        fd = FrameData(
            frame=frame,
            width=640,
            height=480,
            timestamp=time.time(),
            frame_index=42,
            source="test-source",
        )
        
        assert fd.width == 640
        assert fd.height == 480
        assert fd.frame_index == 42
        assert fd.source == "test-source"
        assert fd.frame is frame

