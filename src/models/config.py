"""
Typed configuration models matching the YAML config structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class CameraConfig:
    """Camera configuration."""
    backend: str = "opencv"
    device_id: Union[int, str] = 0
    secrets_file: Optional[str] = None
    resolution: List[int] = field(default_factory=lambda: [1280, 720])
    fps: int = 30
    swap_rb: bool = False
    rotate: int = 0
    flip_horizontal: bool = False
    flip_vertical: bool = False

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CameraConfig":
        """Adapter: Create from config dictionary."""
        return cls(
            backend=d.get("backend", "opencv"),
            device_id=d.get("device_id", 0),
            secrets_file=d.get("secrets_file"),
            resolution=d.get("resolution", [1280, 720]),
            fps=d.get("fps", 30),
            swap_rb=d.get("swap_rb", False),
            rotate=d.get("rotate", 0),
            flip_horizontal=d.get("flip_horizontal", False),
            flip_vertical=d.get("flip_vertical", False),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "device_id": self.device_id,
            "secrets_file": self.secrets_file,
            "resolution": self.resolution,
            "fps": self.fps,
            "swap_rb": self.swap_rb,
            "rotate": self.rotate,
            "flip_horizontal": self.flip_horizontal,
            "flip_vertical": self.flip_vertical,
        }


@dataclass
class YoloConfig:
    """YOLO detector configuration."""
    model: str = ""
    conf_threshold: float = 0.25
    iou_threshold: float = 0.45
    classes: Optional[List[int]] = None
    class_name_overrides: Optional[Dict[int, str]] = None
    class_thresholds: Optional[Dict[int, float]] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "YoloConfig":
        return cls(
            model=d.get("model", ""),
            conf_threshold=d.get("conf_threshold", 0.25),
            iou_threshold=d.get("iou_threshold", 0.45),
            classes=d.get("classes"),
            class_name_overrides=d.get("class_name_overrides"),
            class_thresholds=d.get("class_thresholds"),
        )

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "model": self.model,
            "conf_threshold": self.conf_threshold,
            "iou_threshold": self.iou_threshold,
        }
        if self.classes is not None:
            d["classes"] = self.classes
        if self.class_name_overrides is not None:
            d["class_name_overrides"] = self.class_name_overrides
        if self.class_thresholds is not None:
            d["class_thresholds"] = self.class_thresholds
        return d


@dataclass
class DetectionConfig:
    """Detection configuration."""
    backend: str = "bgsub"
    min_contour_area: int = 1000
    detect_shadows: bool = True
    yolo: Optional[YoloConfig] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DetectionConfig":
        yolo_dict = d.get("yolo")
        yolo = YoloConfig.from_dict(yolo_dict) if yolo_dict else None
        return cls(
            backend=d.get("backend", "bgsub"),
            min_contour_area=d.get("min_contour_area", 1000),
            detect_shadows=d.get("detect_shadows", True),
            yolo=yolo,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "backend": self.backend,
            "min_contour_area": self.min_contour_area,
            "detect_shadows": self.detect_shadows,
        }
        if self.yolo:
            d["yolo"] = self.yolo.to_dict()
        return d


@dataclass
class GateConfig:
    """Gate counting constraints."""
    max_gap_frames: int = 30
    min_age_frames: int = 3
    min_displacement_px: float = 15.0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GateConfig":
        return cls(
            max_gap_frames=d.get("max_gap_frames", 30),
            min_age_frames=d.get("min_age_frames", 3),
            min_displacement_px=d.get("min_displacement_px", 15.0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_gap_frames": self.max_gap_frames,
            "min_age_frames": self.min_age_frames,
            "min_displacement_px": self.min_displacement_px,
        }


# Line definition: either ratio [[x1,y1],[x2,y2]] or single float for horizontal
LineDefinition = Union[float, List[List[float]]]


@dataclass
class CountingConfig:
    """Counting strategy configuration."""
    line_a: Optional[LineDefinition] = None
    line_b: Optional[LineDefinition] = None
    direction_labels: Dict[str, str] = field(default_factory=lambda: {
        "a_to_b": "northbound",
        "b_to_a": "southbound",
    })
    gate: Optional[GateConfig] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CountingConfig":
        gate_dict = d.get("gate")
        gate = GateConfig.from_dict(gate_dict) if gate_dict else None
        return cls(
            line_a=d.get("line_a"),
            line_b=d.get("line_b"),
            direction_labels=d.get("direction_labels", {"a_to_b": "northbound", "b_to_a": "southbound"}),
            gate=gate,
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "direction_labels": self.direction_labels,
        }
        if self.line_a is not None:
            d["line_a"] = self.line_a
        if self.line_b is not None:
            d["line_b"] = self.line_b
        if self.gate:
            d["gate"] = self.gate.to_dict()
        return d


@dataclass
class StorageConfig:
    """Storage configuration."""
    local_database_path: str = "data/database.sqlite"
    retention_days: int = 30
    use_cloud_storage: bool = False
    sync_enabled: bool = False

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StorageConfig":
        return cls(
            local_database_path=d.get("local_database_path", "data/database.sqlite"),
            retention_days=d.get("retention_days", 30),
            use_cloud_storage=d.get("use_cloud_storage", False),
            sync_enabled=d.get("sync_enabled", False),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "local_database_path": self.local_database_path,
            "retention_days": self.retention_days,
            "use_cloud_storage": self.use_cloud_storage,
            "sync_enabled": self.sync_enabled,
        }


@dataclass
class TrackingConfig:
    """Tracking configuration."""
    max_frames_since_seen: int = 10
    min_trajectory_length: int = 3
    iou_threshold: float = 0.3

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TrackingConfig":
        return cls(
            max_frames_since_seen=d.get("max_frames_since_seen", 10),
            min_trajectory_length=d.get("min_trajectory_length", 3),
            iou_threshold=d.get("iou_threshold", 0.3),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_frames_since_seen": self.max_frames_since_seen,
            "min_trajectory_length": self.min_trajectory_length,
            "iou_threshold": self.iou_threshold,
        }


@dataclass
class Config:
    """
    Complete application configuration.
    
    This is a typed representation of the YAML config structure.
    """
    camera: CameraConfig = field(default_factory=CameraConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    counting: Optional[CountingConfig] = None
    storage: StorageConfig = field(default_factory=StorageConfig)
    tracking: Optional[TrackingConfig] = None
    log_path: str = "logs/traffic_monitor.log"
    log_level: str = "INFO"

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Config":
        """Adapter: Create Config from raw dictionary (e.g., from load_config)."""
        camera = CameraConfig.from_dict(d.get("camera", {}))
        detection = DetectionConfig.from_dict(d.get("detection", {}))
        counting_dict = d.get("counting")
        counting = CountingConfig.from_dict(counting_dict) if counting_dict else None
        storage = StorageConfig.from_dict(d.get("storage", {}))
        tracking_dict = d.get("tracking")
        tracking = TrackingConfig.from_dict(tracking_dict) if tracking_dict else None
        
        return cls(
            camera=camera,
            detection=detection,
            counting=counting,
            storage=storage,
            tracking=tracking,
            log_path=d.get("log_path", "logs/traffic_monitor.log"),
            log_level=d.get("log_level", "INFO"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert back to dictionary (for saving or passing to existing code)."""
        d: Dict[str, Any] = {
            "camera": self.camera.to_dict(),
            "detection": self.detection.to_dict(),
            "storage": self.storage.to_dict(),
            "log_path": self.log_path,
            "log_level": self.log_level,
        }
        if self.counting:
            d["counting"] = self.counting.to_dict()
        if self.tracking:
            d["tracking"] = self.tracking.to_dict()
        return d

