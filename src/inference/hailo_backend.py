"""
Hailo AI HAT+ inference backend for Raspberry Pi 5.

This backend uses HailoRT to run YOLOv8 inference on the Hailo-8 NPU.
Requires: Raspberry Pi 5 + AI HAT+ with 'hailo-all' package installed.

Architecture:
- Loads compiled HEF (Hailo Executable Format) model
- Runs inference on Hailo NPU
- Post-processes detections (NMS, coordinate scaling)
- Returns Detection objects matching YOLO backend format

For dev machines without Hailo: Use 'yolo' backend instead.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import cv2
import numpy as np

from .backend import Detection, InferenceBackend


@dataclass(frozen=True)
class HailoConfig:
    """Configuration for Hailo inference backend."""
    
    hef_path: str  # Path to compiled HEF model (e.g., "data/artifacts/yolov8s.hef")
    input_size: tuple[int, int] = (640, 640)  # Model input dimensions (width, height)
    conf_threshold: float = 0.25  # Baseline confidence threshold
    iou_threshold: float = 0.45  # NMS IoU threshold
    classes: Optional[Sequence[int]] = None  # COCO class IDs to detect
    class_name_overrides: Optional[Dict[int, str]] = None  # Human-readable class names
    class_thresholds: Optional[Dict[int, float]] = None  # Class-specific confidence thresholds
    
    # COCO class names (YOLO default)
    # Used if class_name_overrides not provided
    coco_names: Dict[int, str] = None  # Will be set to default COCO names in __post_init__
    
    def __post_init__(self):
        # Default COCO class names for traffic monitoring
        if self.coco_names is None:
            object.__setattr__(self, 'coco_names', {
                0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle',
                5: 'bus', 7: 'truck'
            })


class HailoBackend(InferenceBackend):
    """
    Hailo NPU inference backend for YOLOv8.
    
    Requires:
    - Raspberry Pi 5 with AI HAT+ (Hailo-8L)
    - System package: sudo apt install hailo-all
    - Compiled HEF model (see docs/DEPLOYMENT.md for compilation)
    
    Performance target: 15-25 FPS @ 640x640 on Pi 5
    """
    
    def __init__(self, cfg: HailoConfig):
        self.cfg = cfg
        self._inference_count = 0
        self._total_inference_time = 0.0
        
        try:
            # Import HailoRT Python bindings (installed via system package)
            from hailo_platform import (
                VDevice,
                HailoStreamInterface,
                InferVStreams,
                ConfigureParams,
                InputVStreamParams,
                OutputVStreamParams,
                FormatType
            )
            self._hailo_available = True
            
            logging.info(f"Loading Hailo model from: {cfg.hef_path}")
            
            # Initialize Hailo device
            params = VDevice.create_params()
            self._vdevice = VDevice(params)
            
            # Load HEF model
            self._network_group = self._vdevice.configure(
                cfg.hef_path,
                ConfigureParams.create_from_network_group()
            )[0]
            
            # Get input/output stream information
            self._network_group_params = self._network_group.create_params()
            self._input_vstreams_params = self._network_group_params.input_vstreams_params
            self._output_vstreams_params = self._network_group_params.output_vstreams_params
            
            # Create input/output virtual streams
            self._input_vstream_info = self._network_group.get_input_vstream_infos()[0]
            self._output_vstream_infos = self._network_group.get_output_vstream_infos()
            
            logging.info(f"Hailo backend initialized: {self._input_vstream_info.name}")
            logging.info(f"Hailo input shape: {self._input_vstream_info.shape}")
            logging.info(f"Hailo output streams: {len(self._output_vstream_infos)}")
            
        except ImportError as e:
            self._hailo_available = False
            raise ImportError(
                "HailoRT Python bindings not found. "
                "Install on Raspberry Pi 5 with: sudo apt install hailo-all\n"
                "For development machines, use detection.backend='yolo' instead."
            ) from e
        except FileNotFoundError as e:
            self._hailo_available = False
            raise FileNotFoundError(
                f"Hailo HEF model not found at: {cfg.hef_path}\n"
                "Compile YOLOv8 to HEF format using Hailo Dataflow Compiler.\n"
                "See docs/DEPLOYMENT.md for model compilation instructions."
            ) from e
        except Exception as e:
            self._hailo_available = False
            raise RuntimeError(
                f"Failed to initialize Hailo backend: {e}\n"
                "Ensure AI HAT+ is properly connected and hailo-all package is installed."
            ) from e
    
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Detect objects in frame using Hailo NPU.
        
        Pipeline:
        1. Preprocess: Resize + letterbox to model input size
        2. Inference: Run on Hailo NPU
        3. Post-process: Parse YOLO outputs, apply NMS
        4. Filter: Apply class-specific confidence thresholds
        5. Scale: Map coordinates back to original frame
        
        Args:
            frame: Input frame (BGR numpy array, any size)
            
        Returns:
            List of Detection objects with original frame coordinates
        """
        if not self._hailo_available:
            logging.warning("Hailo backend not available, returning empty detections")
            return []
        
        start_time = time.perf_counter()
        
        try:
            # 1. Preprocess frame for model input
            input_tensor, scale, pad_w, pad_h = self._preprocess(frame)
            
            # 2. Run inference on Hailo NPU
            raw_outputs = self._infer(input_tensor)
            
            # 3. Post-process YOLO outputs (parse + NMS)
            detections = self._postprocess(
                raw_outputs,
                scale=scale,
                pad_w=pad_w,
                pad_h=pad_h,
                orig_h=frame.shape[0],
                orig_w=frame.shape[1]
            )
            
            # 4. Apply class-specific confidence thresholds
            filtered_detections = self._apply_class_thresholds(detections)
            
            # Track performance metrics
            inference_time = time.perf_counter() - start_time
            self._inference_count += 1
            self._total_inference_time += inference_time
            
            # Log FPS periodically (every 100 frames)
            if self._inference_count % 100 == 0:
                avg_fps = self._inference_count / self._total_inference_time
                logging.info(f"Hailo inference: {avg_fps:.1f} FPS (avg over {self._inference_count} frames)")
            
            return filtered_detections
            
        except Exception as e:
            logging.error(f"Hailo inference failed: {e}")
            return []
    
    def _preprocess(self, frame: np.ndarray) -> tuple[np.ndarray, float, int, int]:
        """
        Preprocess frame for YOLO input.
        
        Applies letterbox resize to maintain aspect ratio.
        
        Returns:
            (input_tensor, scale, pad_w, pad_h)
        """
        target_h, target_w = self.cfg.input_size[1], self.cfg.input_size[0]
        orig_h, orig_w = frame.shape[:2]
        
        # Calculate scale to fit image into target size
        scale = min(target_w / orig_w, target_h / orig_h)
        
        # Resize with aspect ratio preserved
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Create letterbox canvas
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        
        # Center image in canvas
        pad_w = (target_w - new_w) // 2
        pad_h = (target_h - new_h) // 2
        canvas[pad_h:pad_h + new_h, pad_w:pad_w + new_w] = resized
        
        # Convert BGR to RGB (YOLO expects RGB)
        canvas_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        
        # Normalize to [0, 1] and convert to float32
        input_tensor = canvas_rgb.astype(np.float32) / 255.0
        
        # Transpose to NCHW format (Hailo expects channels-first)
        input_tensor = np.transpose(input_tensor, (2, 0, 1))  # HWC -> CHW
        input_tensor = np.expand_dims(input_tensor, axis=0)  # Add batch dimension
        
        return input_tensor, scale, pad_w, pad_h
    
    def _infer(self, input_tensor: np.ndarray) -> List[np.ndarray]:
        """
        Run inference on Hailo NPU.
        
        Returns:
            List of raw output tensors from model
        """
        from hailo_platform import InferVStreams
        
        # Create inference context with virtual streams
        with InferVStreams(self._network_group, self._input_vstreams_params, self._output_vstreams_params) as infer_pipeline:
            # Prepare input data (dict mapping input name to tensor)
            input_data = {self._input_vstream_info.name: input_tensor}
            
            # Run inference
            with self._network_group.activate(self._network_group_params):
                output_data = infer_pipeline.infer(input_data)
            
            # Extract output tensors
            outputs = [output_data[info.name] for info in self._output_vstream_infos]
            
        return outputs
    
    def _postprocess(
        self,
        raw_outputs: List[np.ndarray],
        scale: float,
        pad_w: int,
        pad_h: int,
        orig_h: int,
        orig_w: int
    ) -> List[Detection]:
        """
        Post-process YOLO outputs.
        
        YOLOv8 outputs 3 feature maps with different scales.
        Each detection: [x, y, w, h, class_confidences...]
        
        Args:
            raw_outputs: List of output tensors from model
            scale: Resize scale factor
            pad_w, pad_h: Letterbox padding
            orig_h, orig_w: Original frame dimensions
            
        Returns:
            List of Detection objects with NMS applied
        """
        # Collect all detections from all output layers
        all_boxes = []
        all_scores = []
        all_class_ids = []
        
        for output in raw_outputs:
            # Parse YOLO output format
            # Expected shape: (batch, num_anchors, 4 + num_classes)
            # Where 4 = [x_center, y_center, width, height]
            
            if output.ndim == 3:
                output = output[0]  # Remove batch dimension
            
            # Extract bounding boxes and class scores
            # Note: Actual format depends on HEF compilation settings
            # This is a placeholder - adjust based on actual output format
            num_detections = output.shape[0]
            
            for i in range(num_detections):
                detection = output[i]
                
                # Parse detection (format depends on model compilation)
                # Standard YOLOv8: [x, y, w, h, conf, class_scores...]
                x_center, y_center, width, height = detection[:4]
                class_scores = detection[4:]
                
                # Find best class
                class_id = np.argmax(class_scores)
                confidence = class_scores[class_id]
                
                # Filter by confidence
                if confidence < self.cfg.conf_threshold:
                    continue
                
                # Filter by class if specified
                if self.cfg.classes is not None and class_id not in self.cfg.classes:
                    continue
                
                # Convert center format to corner format
                x1 = x_center - width / 2
                y1 = y_center - height / 2
                x2 = x_center + width / 2
                y2 = y_center + height / 2
                
                # Scale back to original frame coordinates
                x1 = (x1 - pad_w) / scale
                y1 = (y1 - pad_h) / scale
                x2 = (x2 - pad_w) / scale
                y2 = (y2 - pad_h) / scale
                
                # Clip to frame bounds
                x1 = max(0, min(x1, orig_w))
                y1 = max(0, min(y1, orig_h))
                x2 = max(0, min(x2, orig_w))
                y2 = max(0, min(y2, orig_h))
                
                all_boxes.append([x1, y1, x2, y2])
                all_scores.append(confidence)
                all_class_ids.append(class_id)
        
        if not all_boxes:
            return []
        
        # Apply Non-Maximum Suppression
        boxes = np.array(all_boxes, dtype=np.float32)
        scores = np.array(all_scores, dtype=np.float32)
        class_ids = np.array(all_class_ids, dtype=np.int32)
        
        indices = self._nms(boxes, scores, self.cfg.iou_threshold)
        
        # Build Detection objects
        detections = []
        for idx in indices:
            class_id = int(class_ids[idx])
            class_name = self._get_class_name(class_id)
            
            detections.append(Detection(
                x1=float(boxes[idx][0]),
                y1=float(boxes[idx][1]),
                x2=float(boxes[idx][2]),
                y2=float(boxes[idx][3]),
                confidence=float(scores[idx]),
                class_id=class_id,
                class_name=class_name
            ))
        
        return detections
    
    def _nms(self, boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> List[int]:
        """
        Non-Maximum Suppression.
        
        Args:
            boxes: Array of boxes (N, 4) in [x1, y1, x2, y2] format
            scores: Array of confidence scores (N,)
            iou_threshold: IoU threshold for suppression
            
        Returns:
            List of indices to keep
        """
        if len(boxes) == 0:
            return []
        
        # Use OpenCV's NMS (fast, C++ implementation)
        indices = cv2.dnn.NMSBoxes(
            bboxes=boxes.tolist(),
            scores=scores.tolist(),
            score_threshold=0.0,  # Already filtered by conf_threshold
            nms_threshold=iou_threshold
        )
        
        if len(indices) > 0:
            return indices.flatten().tolist()
        return []
    
    def _apply_class_thresholds(self, detections: List[Detection]) -> List[Detection]:
        """
        Apply class-specific confidence thresholds.
        
        Same logic as YOLO backend for consistency.
        """
        if not self.cfg.class_thresholds:
            return detections
        
        filtered = []
        for det in detections:
            if det.class_id is not None:
                class_threshold = self.cfg.class_thresholds.get(
                    det.class_id,
                    self.cfg.conf_threshold
                )
                if det.confidence >= class_threshold:
                    filtered.append(det)
            else:
                filtered.append(det)
        
        return filtered
    
    def _get_class_name(self, class_id: int) -> str:
        """Get human-readable class name."""
        if self.cfg.class_name_overrides:
            return self.cfg.class_name_overrides.get(class_id, str(class_id))
        return self.cfg.coco_names.get(class_id, str(class_id))
    
    def get_average_fps(self) -> float:
        """Get average inference FPS."""
        if self._total_inference_time == 0:
            return 0.0
        return self._inference_count / self._total_inference_time


