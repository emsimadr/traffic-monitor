from __future__ import annotations

import os
import platform
import time
from dataclasses import dataclass
from typing import Any, Dict


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


