from __future__ import annotations

import os
import platform
import time
import shutil
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class HealthService:
    cfg: Dict[str, Any]

    def get_health_summary(self) -> Dict[str, Any]:
        # Keep v0 lightweight and dependency-free; can add psutil later.
        storage_path = self.cfg.get("storage", {}).get("local_database_path")
        log_path = self.cfg.get("log_path")
        return {
            "timestamp": time.time(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cwd": os.getcwd(),
            "storage_db_path": storage_path,
            "log_path": log_path,
        }

    @staticmethod
    def disk_usage(path: Optional[str] = None) -> Dict[str, Any]:
        """
        Lightweight disk stats for status/health endpoints.
        """
        target = path or "."
        try:
            usage = shutil.disk_usage(target)
            used = usage.total - usage.free
            pct_free = (usage.free / usage.total * 100) if usage.total else None
            return {
                "total_bytes": usage.total,
                "used_bytes": used,
                "free_bytes": usage.free,
                "pct_free": pct_free,
            }
        except Exception:
            return {
                "total_bytes": None,
                "used_bytes": None,
                "free_bytes": None,
                "pct_free": None,
                "error": "disk_usage_failed",
            }

    @staticmethod
    def read_cpu_temp_c() -> Optional[float]:
        """
        Best-effort CPU temperature read; returns None if unavailable.
        """
        candidates = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/class/hwmon/hwmon0/temp1_input",
        ]
        for path in candidates:
            try:
                if os.path.exists(path):
                    with open(path, "r") as f:
                        raw = f.read().strip()
                        temp_c = float(raw) / 1000.0 if len(raw) > 3 else float(raw)
                        return temp_c
            except Exception:
                continue
        return None


