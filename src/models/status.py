"""
Status and SystemStats models for system monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class StatusLevel(str, Enum):
    """System status levels."""
    RUNNING = "running"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass
class DiskUsage:
    """
    Disk usage statistics.
    
    Attributes:
        total_bytes: Total disk space.
        used_bytes: Used disk space.
        free_bytes: Free disk space.
        pct_free: Percentage of free space (0-100).
    """
    total_bytes: Optional[int] = None
    used_bytes: Optional[int] = None
    free_bytes: Optional[int] = None
    pct_free: Optional[float] = None
    error: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DiskUsage":
        """Adapter: Create from dictionary (e.g., from HealthService.disk_usage)."""
        return cls(
            total_bytes=d.get("total_bytes"),
            used_bytes=d.get("used_bytes"),
            free_bytes=d.get("free_bytes"),
            pct_free=d.get("pct_free"),
            error=d.get("error"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = {
            "total_bytes": self.total_bytes,
            "used_bytes": self.used_bytes,
            "free_bytes": self.free_bytes,
            "pct_free": self.pct_free,
        }
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class SystemStats:
    """
    Runtime system statistics.
    
    Attributes:
        fps: Current frames per second.
        cpu_usage: CPU usage percentage (0-100).
        memory_usage: Memory usage percentage (0-100).
        start_time: Unix timestamp when system started.
        last_frame_ts: Unix timestamp of last processed frame.
    """
    fps: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    start_time: Optional[float] = None
    last_frame_ts: Optional[float] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SystemStats":
        """Adapter: Create from dictionary (e.g., from SharedState.system_stats)."""
        return cls(
            fps=d.get("fps", 0.0),
            cpu_usage=d.get("cpu_usage", 0.0),
            memory_usage=d.get("memory_usage", 0.0),
            start_time=d.get("start_time"),
            last_frame_ts=d.get("last_frame_ts"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "fps": self.fps,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "start_time": self.start_time,
            "last_frame_ts": self.last_frame_ts,
        }


@dataclass
class Status:
    """
    Aggregate system status for monitoring/UI.
    
    Attributes:
        status: Current status level (running/degraded/offline).
        alerts: List of active alert codes.
        last_frame_age: Seconds since last frame was processed.
        fps: Current frames per second.
        uptime_seconds: Seconds since system started.
        disk: Disk usage statistics.
        temp_c: CPU temperature in Celsius.
        timestamp: Unix timestamp of this status snapshot.
    """
    status: StatusLevel
    alerts: List[str] = field(default_factory=list)
    last_frame_age: Optional[float] = None
    fps: float = 0.0
    uptime_seconds: Optional[int] = None
    disk: Optional[DiskUsage] = None
    temp_c: Optional[float] = None
    timestamp: float = 0.0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Status":
        """Adapter: Create from dictionary (e.g., from /api/status response)."""
        disk_dict = d.get("disk")
        disk = DiskUsage.from_dict(disk_dict) if disk_dict else None
        
        status_str = d.get("status", "offline")
        try:
            status_level = StatusLevel(status_str)
        except ValueError:
            status_level = StatusLevel.OFFLINE
        
        return cls(
            status=status_level,
            alerts=d.get("alerts", []),
            last_frame_age=d.get("last_frame_age"),
            fps=d.get("fps", 0.0),
            uptime_seconds=d.get("uptime_seconds"),
            disk=disk,
            temp_c=d.get("temp_c"),
            timestamp=d.get("timestamp", 0.0),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "alerts": self.alerts,
            "last_frame_age": self.last_frame_age,
            "fps": self.fps,
            "uptime_seconds": self.uptime_seconds,
            "disk": self.disk.to_dict() if self.disk else None,
            "temp_c": self.temp_c,
            "timestamp": self.timestamp,
        }

    @property
    def is_healthy(self) -> bool:
        """True if status is running with no alerts."""
        return self.status == StatusLevel.RUNNING and len(self.alerts) == 0

