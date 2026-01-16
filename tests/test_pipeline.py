"""
Tests for the pipeline engine.
"""

import time
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from collections import deque

from pipeline.engine import PipelineEngine, PipelineConfig, create_engine_from_config
from pipeline.stages.measure import MeasureStage, MeasureStageConfig
from observation.base import ObservationSource, ObservationConfig
from models.frame import FrameData


class MockObservationSource(ObservationSource):
    """Mock source for testing."""
    
    def __init__(self, config: ObservationConfig, frames: list = None, max_frames: int = 10):
        super().__init__(config)
        self._frames = frames
        self._max_frames = max_frames
        self._pos = 0
    
    def open(self) -> None:
        self._is_open = True
        self._pos = 0
        self._frame_index = 0
    
    def read(self) -> FrameData | None:
        if not self._is_open:
            return None
        
        if self._frames is not None:
            if self._pos >= len(self._frames):
                return None
            frame = self._frames[self._pos]
        else:
            if self._pos >= self._max_frames:
                return None
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
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


class MockDetector:
    """Mock detector for testing."""
    
    def detect(self, frame):
        # Return empty list (no detections)
        return []


class MockTracker:
    """Mock tracker for testing."""
    
    def update(self, detections, counting_line=None, detection_metadata=None):
        return []
    
    def get_active_tracks(self):
        return []
    
    def get_all_tracks(self):
        return []


class MockDatabase:
    """Mock database for testing."""
    
    def add_vehicle_detection(self, **kwargs):
        pass
    
    def update_hourly_counts(self):
        pass
    
    def update_daily_counts(self):
        pass
    
    def cleanup_old_data(self, retention_days):
        pass


class MockWebState:
    """Mock web state for testing."""
    
    def __init__(self):
        self.frames = []
        self.stats = {}
    
    def set_frame(self, frame):
        self.frames.append(frame)
    
    def update_system_stats(self, stats):
        self.stats.update(stats)


class MockMeasureStage(MeasureStage):
    """Mock measure stage for testing."""
    
    def __init__(self):
        # Don't call super().__init__ to avoid needing real config
        self._config = MeasureStageConfig()
        self._db = None
        self._counter = None
        self._frame_size = None
        self.processed_frames = 0
        self._counted_ids = set()
    
    def ensure_counter(self, frame_w, frame_h):
        pass  # No-op for mock
    
    def process(self, tracks, frame_idx):
        self.processed_frames += 1
        return []  # No events
    
    def get_gate_lines(self):
        return None, None
    
    def is_counted(self, track_id):
        return track_id in self._counted_ids


class TestPipelineConfig:
    def test_default_values(self):
        config = PipelineConfig()
        assert config.max_consecutive_failures == 10
        assert config.stats_log_interval == 60.0
        assert config.display is False
        assert config.record is False

    def test_custom_values(self):
        config = PipelineConfig(
            max_consecutive_failures=5,
            display=True,
            record=True,
            output_dir="/tmp/videos",
        )
        assert config.max_consecutive_failures == 5
        assert config.display is True
        assert config.output_dir == "/tmp/videos"


class TestPipelineEngine:
    def _create_mock_ctx(self):
        """Create a mock RuntimeContext."""
        ctx = MagicMock()
        ctx.detector = MockDetector()
        ctx.tracker = MockTracker()
        ctx.db = MockDatabase()
        ctx.web_state = MockWebState()
        ctx.cloud_sync = None
        ctx.config = {
            "camera": {"fps": 30, "resolution": [640, 480]},
            "storage": {"retention_days": 30},
        }
        # Mock update_frame to actually call web_state
        def update_frame(frame, fps):
            ctx.web_state.set_frame(frame)
            ctx.web_state.update_system_stats({"fps": fps})
        ctx.update_frame = update_frame
        return ctx

    def test_engine_processes_frames(self):
        """Engine processes frames through the pipeline."""
        source_config = ObservationConfig(source_id="test")
        source = MockObservationSource(source_config, max_frames=3)
        ctx = self._create_mock_ctx()
        measure = MockMeasureStage()
        config = PipelineConfig()
        
        engine = PipelineEngine(source, ctx, measure, config)
        engine.run()
        
        # Should have processed 3 frames
        assert measure.processed_frames == 3
        assert engine.stats.frame_count == 3

    def test_engine_stops_on_failures(self):
        """Engine stops after max consecutive failures."""
        source_config = ObservationConfig(source_id="test")
        # Source that always returns None (simulates failure)
        source = MockObservationSource(source_config, frames=[])
        ctx = self._create_mock_ctx()
        measure = MockMeasureStage()
        config = PipelineConfig(max_consecutive_failures=3)
        
        engine = PipelineEngine(source, ctx, measure, config)
        
        # Patch time.sleep to speed up test
        with patch('time.sleep'):
            engine.run()
        
        # Should have stopped after 3 failures
        assert engine.stats.consecutive_failures >= 3

    def test_engine_callbacks(self):
        """Engine calls registered callbacks."""
        source_config = ObservationConfig(source_id="test")
        source = MockObservationSource(source_config, max_frames=2)
        ctx = self._create_mock_ctx()
        measure = MockMeasureStage()
        config = PipelineConfig()
        
        callback_calls = []
        def my_callback(frame_data, events):
            callback_calls.append((frame_data.frame_index, events))
        
        engine = PipelineEngine(source, ctx, measure, config)
        engine.add_callback(my_callback)
        engine.run()
        
        assert len(callback_calls) == 2
        assert callback_calls[0][0] == 1
        assert callback_calls[1][0] == 2

    def test_engine_updates_web_state(self):
        """Engine updates web state with frames."""
        source_config = ObservationConfig(source_id="test")
        source = MockObservationSource(source_config, max_frames=2)
        ctx = self._create_mock_ctx()
        measure = MockMeasureStage()
        config = PipelineConfig()
        
        engine = PipelineEngine(source, ctx, measure, config)
        engine.run()
        
        # Web state should have received frames
        assert len(ctx.web_state.frames) == 2
        assert "fps" in ctx.web_state.stats


class TestCreateEngineFromConfig:
    def test_creates_engine(self):
        """Factory creates engine from config dict."""
        config = {
            "camera": {
                "backend": "opencv",
                "device_id": 0,
                "resolution": [640, 480],
                "fps": 30,
            },
            "storage": {"retention_days": 7},
        }
        
        ctx = MagicMock()
        ctx.config = config
        ctx.db = MagicMock()  # For MeasureStage
        
        engine = create_engine_from_config(
            config=config,
            ctx=ctx,
            display=True,
            record=False,
        )
        
        assert engine is not None
        assert engine.source.source_id == "main-camera"
        assert engine.config.display is True
        assert engine.config.record is False

