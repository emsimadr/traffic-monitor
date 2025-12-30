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
    direction_labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Direction code to label mapping from config"
    )
    cpu_temp_c: Optional[float] = Field(None, description="CPU temperature in Celsius")
    disk_free_pct: Optional[float] = Field(None, description="Disk free percentage")
    warnings: list[str] = Field(default_factory=list, description="Active warnings")


