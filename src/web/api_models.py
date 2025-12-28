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


