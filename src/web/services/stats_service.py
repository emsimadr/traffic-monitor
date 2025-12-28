from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class StatsService:
    db_path: str

    def get_summary(self) -> Dict[str, Any]:
        now = time.time()
        last_hour_start = now - 3600
        last_24h_start = now - 86400

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM vehicle_detections")
            total = int(cur.fetchone()[0] or 0)

            cur.execute(
                "SELECT COUNT(*) FROM vehicle_detections WHERE timestamp >= ?",
                (last_hour_start,),
            )
            last_hour = int(cur.fetchone()[0] or 0)

            cur.execute(
                "SELECT COUNT(*) FROM vehicle_detections WHERE timestamp >= ?",
                (last_24h_start,),
            )
            last_24h = int(cur.fetchone()[0] or 0)

            cur.execute(
                "SELECT direction, COUNT(*) FROM vehicle_detections WHERE timestamp >= ? GROUP BY direction",
                (last_24h_start,),
            )
            by_direction = {row[0] or "unknown": int(row[1]) for row in cur.fetchall()}

        return {
            "total_detections": total,
            "last_hour": last_hour,
            "last_24h": last_24h,
            "last_24h_by_direction": by_direction,
        }


