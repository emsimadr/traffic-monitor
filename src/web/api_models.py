from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field


class StatsSummary(BaseModel):
    total_detections: int
    last_hour: int
    last_24h: int
    last_24h_by_direction: Dict[str, int]


class LiveStatsResponse(BaseModel):
    total_vehicles: int
    last_hour: int
    fps: float
    uptime_seconds: int
    cloud_enabled: bool
    last_24h_by_direction: Dict[str, int]
    last_hour_by_direction: Dict[str, int]


class RangeStatsResponse(BaseModel):
    start_ts: float
    end_ts: float
    total: int
    by_direction: Dict[str, int]


class StatusResponse(BaseModel):
    status: str = Field(..., description="running|degraded|offline")
    alerts: list[str]
    last_frame_age: Optional[float]
    fps: float
    uptime_seconds: Optional[int]
    disk: Dict[str, float]
    temp_c: Optional[float]
    stats: StatsSummary
    health: Dict[str, object]
    timestamp: float


class CompactStatusResponse(BaseModel):
    """
    Compact status response optimized for frontend polling (every 2s).
    Includes only essential fields for dashboard display.
    """
    running: bool = Field(..., description="True if system is operational")
    last_frame_age_s: Optional[float] = Field(None, description="Seconds since last frame")
    fps_capture: Optional[float] = Field(None, description="Camera capture FPS")
    fps_infer: Optional[float] = Field(None, description="Inference FPS (if applicable)")
    infer_latency_ms_p50: Optional[float] = Field(None, description="Inference latency p50")
    infer_latency_ms_p95: Optional[float] = Field(None, description="Inference latency p95")
    counts_today_total: int = Field(0, description="Total counts today")
    counts_by_direction_code: Dict[str, int] = Field(
        default_factory=dict, 
        description="Counts by direction code (A_TO_B, B_TO_A)"
    )
    counts_by_class: Dict[str, int] = Field(
        default_factory=dict,
        description="Counts by class today (car, bicycle, person, etc.)"
    )
    direction_labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Direction code to label mapping from config"
    )
    cpu_temp_c: Optional[float] = Field(None, description="CPU temperature in Celsius")
    disk_free_pct: Optional[float] = Field(None, description="Disk free percentage")
    warnings: list[str] = Field(default_factory=list, description="Active warnings")


class CountEvent(BaseModel):
    """Single count event for /api/stats/recent."""
    ts: int = Field(..., description="Timestamp in milliseconds")
    direction_code: str = Field(..., description="Direction code (A_TO_B, B_TO_A)")
    direction_label: Optional[str] = Field(None, description="Human-readable direction label")
    class_name: Optional[str] = Field(None, description="Detected class (car, bicycle, person, etc.)")
    confidence: float = Field(1.0, description="Detection confidence")


class RecentEventsResponse(BaseModel):
    """Response for /api/stats/recent."""
    events: list[CountEvent]
    total_shown: int


class HourlyCount(BaseModel):
    """Hourly aggregate."""
    hour_start_ts: int = Field(..., description="Hour start timestamp (Unix seconds)")
    total: int = Field(0, description="Total counts in this hour")
    by_direction: Dict[str, int] = Field(default_factory=dict, description="Breakdown by direction")
    by_class: Dict[str, int] = Field(default_factory=dict, description="Breakdown by class")


class HourlyStatsResponse(BaseModel):
    """Response for /api/stats/hourly."""
    hours: list[HourlyCount]
    start_ts: float
    end_ts: float


class DailyCount(BaseModel):
    """Daily aggregate."""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    day_start_ts: int = Field(..., description="Day start timestamp (Unix seconds)")
    total: int = Field(0, description="Total counts in this day")
    by_direction: Dict[str, int] = Field(default_factory=dict)
    by_class: Dict[str, int] = Field(default_factory=dict)


class DailyStatsResponse(BaseModel):
    """Response for /api/stats/daily."""
    days: list[DailyCount]
    start_ts: float
    end_ts: float


class PipelineStageStatus(BaseModel):
    """Status of a single pipeline stage."""
    name: str
    status: str = Field(..., description="running|degraded|offline")
    message: Optional[str] = None


class PipelineStatusResponse(BaseModel):
    """Response for /api/status/pipeline."""
    stages: list[PipelineStageStatus]
    overall_status: str


