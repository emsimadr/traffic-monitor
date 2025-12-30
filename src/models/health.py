"""
Health model for system health checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Health:
    """
    System health information.
    
    Attributes:
        timestamp: Unix timestamp of the health check.
        platform: OS/platform description.
        python: Python version.
        cwd: Current working directory.
        storage_db_path: Path to the local SQLite database.
        log_path: Path to the log file.
    """
    timestamp: float
    platform: str
    python: str
    cwd: str
    storage_db_path: Optional[str] = None
    log_path: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Health":
        """Adapter: Create from dictionary (e.g., from HealthService.get_health_summary)."""
        return cls(
            timestamp=d.get("timestamp", 0.0),
            platform=d.get("platform", "unknown"),
            python=d.get("python", "unknown"),
            cwd=d.get("cwd", ""),
            storage_db_path=d.get("storage_db_path"),
            log_path=d.get("log_path"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "platform": self.platform,
            "python": self.python,
            "cwd": self.cwd,
            "storage_db_path": self.storage_db_path,
            "log_path": self.log_path,
        }

