"""
Tests for class-specific confidence thresholds in YOLO detection.
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch

from src.detection.yolo_detector import YoloConfig, UltralyticsYoloDetector
from src.inference.cpu_backend import CpuYoloConfig, UltralyticsCpuBackend


@pytest.fixture
def mock_yolo_model():
    """Create a mock YOLO model that returns test detections."""
    with patch('src.detection.yolo_detector.YOLO') as mock_yolo:
        model_instance = MagicMock()
        mock_yolo.return_value = model_instance
        
        # Mock results with detections at various confidence levels
        mock_results = MagicMock()
        mock_results.names = {0: "person", 1: "bicycle", 2: "car"}
        
        # Create mock boxes with different confidence scores
        mock_boxes = MagicMock()
        # Detections: person (0.22), bicycle (0.28), car (0.38), person (0.18), car (0.50)
        mock_boxes.xyxy = Mock()
        mock_boxes.xyxy.cpu = Mock(return_value=Mock(
            numpy=Mock(return_value=np.array([
                [10, 10, 50, 100],  # person at 0.22 conf
                [60, 20, 100, 80],  # bicycle at 0.28 conf
                [120, 30, 200, 150],  # car at 0.38 conf
                [220, 40, 260, 120],  # person at 0.18 conf
                [280, 50, 350, 180],  # car at 0.50 conf
            ]))
        ))
        
        mock_boxes.conf = Mock()
        mock_boxes.conf.cpu = Mock(return_value=Mock(
            numpy=Mock(return_value=np.array([0.22, 0.28, 0.38, 0.18, 0.50]))
        ))
        
        mock_boxes.cls = Mock()
        mock_boxes.cls.cpu = Mock(return_value=Mock(
            numpy=Mock(return_value=np.array([0, 1, 2, 0, 2]))  # person, bicycle, car, person, car
        ))
        
        mock_results.boxes = mock_boxes
        model_instance.predict.return_value = [mock_results]
        
        yield model_instance


def test_single_threshold_baseline():
    """Test baseline behavior with single threshold (no class-specific thresholds)."""
    with patch('ultralytics.YOLO'):
        config = YoloConfig(
            model="yolov8s.pt",
            conf_threshold=0.25,
            classes=[0, 1, 2],
        )
        detector = UltralyticsYoloDetector(config)
        
        # With single threshold of 0.25:
        # - person at 0.22: REJECTED (below 0.25)
        # - bicycle at 0.28: ACCEPTED
        # - car at 0.38: ACCEPTED
        # - person at 0.18: REJECTED
        # - car at 0.50: ACCEPTED
        # Expected: 3 detections
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        with patch.object(detector._model, 'predict') as mock_predict:
            mock_results = MagicMock()
            mock_results.names = {0: "person", 1: "bicycle", 2: "car"}
            mock_boxes = MagicMock()
            mock_boxes.xyxy = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([
                [60, 20, 100, 80],
                [120, 30, 200, 150],
                [280, 50, 350, 180],
            ])))))
            mock_boxes.conf = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([0.28, 0.38, 0.50])))))
            mock_boxes.cls = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([1, 2, 2])))))
            mock_results.boxes = mock_boxes
            mock_predict.return_value = [mock_results]
            
            detections = detector.detect(frame)
            
        assert len(detections) == 3
        assert detections[0].class_name == "bicycle"
        assert detections[1].class_name == "car"
        assert detections[2].class_name == "car"


def test_class_specific_thresholds_improves_pedestrian_detection():
    """Test that class-specific thresholds allow more pedestrian detections."""
    with patch('ultralytics.YOLO'):
        config = YoloConfig(
            model="yolov8s.pt",
            conf_threshold=0.25,  # Baseline threshold
            classes=[0, 1, 2],
            class_thresholds={
                0: 0.20,  # person - LOWER threshold
                1: 0.25,  # bicycle - same as baseline
                2: 0.40,  # car - HIGHER threshold
            }
        )
        detector = UltralyticsYoloDetector(config)
        
        # With class-specific thresholds:
        # - person at 0.22: ACCEPTED (0.22 >= 0.20)
        # - bicycle at 0.28: ACCEPTED (0.28 >= 0.25)
        # - car at 0.38: REJECTED (0.38 < 0.40)
        # - person at 0.18: REJECTED (0.18 < 0.20)
        # - car at 0.50: ACCEPTED (0.50 >= 0.40)
        # Expected: 3 detections (1 person, 1 bicycle, 1 car)
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        with patch.object(detector._model, 'predict') as mock_predict:
            mock_results = MagicMock()
            mock_results.names = {0: "person", 1: "bicycle", 2: "car"}
            mock_boxes = MagicMock()
            mock_boxes.xyxy = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([
                [10, 10, 50, 100],
                [60, 20, 100, 80],
                [120, 30, 200, 150],
                [220, 40, 260, 120],
                [280, 50, 350, 180],
            ])))))
            mock_boxes.conf = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([0.22, 0.28, 0.38, 0.18, 0.50])))))
            mock_boxes.cls = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([0, 1, 2, 0, 2])))))
            mock_results.boxes = mock_boxes
            mock_predict.return_value = [mock_results]
            
            detections = detector.detect(frame)
        
        assert len(detections) == 3
        assert detections[0].class_name == "person"
        assert detections[0].confidence == pytest.approx(0.22, rel=0.01)
        assert detections[1].class_name == "bicycle"
        assert detections[1].confidence == pytest.approx(0.28, rel=0.01)
        assert detections[2].class_name == "car"
        assert detections[2].confidence == pytest.approx(0.50, rel=0.01)


def test_cpu_backend_class_thresholds():
    """Test class-specific thresholds in CPU backend."""
    with patch('ultralytics.YOLO'):
        config = CpuYoloConfig(
            model="yolov8s.pt",
            conf_threshold=0.25,
            classes=[0, 1, 2],
            class_thresholds={
                0: 0.20,  # person
                1: 0.25,  # bicycle
                2: 0.40,  # car
            }
        )
        backend = UltralyticsCpuBackend(config)
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        with patch.object(backend._model, 'predict') as mock_predict:
            mock_results = MagicMock()
            mock_results.names = {0: "person", 1: "bicycle", 2: "car"}
            mock_boxes = MagicMock()
            mock_boxes.xyxy = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([
                [10, 10, 50, 100],
                [60, 20, 100, 80],
                [280, 50, 350, 180],
            ])))))
            mock_boxes.conf = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([0.22, 0.28, 0.50])))))
            mock_boxes.cls = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([0, 1, 2])))))
            mock_results.boxes = mock_boxes
            mock_predict.return_value = [mock_results]
            
            detections = backend.detect(frame)
        
        assert len(detections) == 3
        assert detections[0].class_name == "person"
        assert detections[1].class_name == "bicycle"
        assert detections[2].class_name == "car"


def test_class_thresholds_none_falls_back_to_baseline():
    """Test that when class_thresholds is None, baseline threshold is used."""
    with patch('ultralytics.YOLO'):
        config = YoloConfig(
            model="yolov8s.pt",
            conf_threshold=0.30,
            classes=[0, 1, 2],
            class_thresholds=None,  # No class-specific thresholds
        )
        detector = UltralyticsYoloDetector(config)
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        with patch.object(detector._model, 'predict') as mock_predict:
            mock_results = MagicMock()
            mock_results.names = {0: "person", 2: "car"}
            mock_boxes = MagicMock()
            # person at 0.25 (below 0.30), car at 0.35 (above 0.30)
            mock_boxes.xyxy = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([
                [10, 10, 50, 100],
                [120, 30, 200, 150],
            ])))))
            mock_boxes.conf = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([0.25, 0.35])))))
            mock_boxes.cls = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([0, 2])))))
            mock_results.boxes = mock_boxes
            mock_predict.return_value = [mock_results]
            
            detections = detector.detect(frame)
        
        # Only car should be detected (person filtered by baseline threshold)
        assert len(detections) == 1
        assert detections[0].class_name == "car"


def test_class_thresholds_partial_coverage():
    """Test that missing class IDs in class_thresholds fall back to baseline."""
    with patch('ultralytics.YOLO'):
        config = YoloConfig(
            model="yolov8s.pt",
            conf_threshold=0.30,  # Baseline
            classes=[0, 1, 2],
            class_thresholds={
                0: 0.20,  # person - override
                # bicycle not specified - should use baseline 0.30
                2: 0.40,  # car - override
            }
        )
        detector = UltralyticsYoloDetector(config)
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        with patch.object(detector._model, 'predict') as mock_predict:
            mock_results = MagicMock()
            mock_results.names = {0: "person", 1: "bicycle", 2: "car"}
            mock_boxes = MagicMock()
            # person at 0.22 (>= 0.20), bicycle at 0.28 (< 0.30), car at 0.45 (>= 0.40)
            mock_boxes.xyxy = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([
                [10, 10, 50, 100],
                [60, 20, 100, 80],
                [120, 30, 200, 150],
            ])))))
            mock_boxes.conf = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([0.22, 0.28, 0.45])))))
            mock_boxes.cls = Mock(cpu=Mock(return_value=Mock(numpy=Mock(return_value=np.array([0, 1, 2])))))
            mock_results.boxes = mock_boxes
            mock_predict.return_value = [mock_results]
            
            detections = detector.detect(frame)
        
        # person and car should pass, bicycle should be filtered
        assert len(detections) == 2
        assert detections[0].class_name == "person"
        assert detections[1].class_name == "car"

