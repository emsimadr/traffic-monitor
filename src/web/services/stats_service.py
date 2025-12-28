from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class StatsService:
    db_path: str
    direction_labels: dict | None = None

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
            raw_dir = {row[0] or "unknown": int(row[1]) for row in cur.fetchall()}

        # Map direction codes to labels if provided
        if self.direction_labels:
            mapped: Dict[str, int] = {}
            for code, count in raw_dir.items():
                if code == "A_TO_B":
                    label = self.direction_labels.get("a_to_b", code)
                elif code == "B_TO_A":
                    label = self.direction_labels.get("b_to_a", code)
                else:
                    label = code
                mapped[label] = mapped.get(label, 0) + count
            by_direction = mapped
        else:
            by_direction = raw_dir

        return {
            "total_detections": total,
            "last_hour": last_hour,
            "last_24h": last_24h,
            "last_24h_by_direction": by_direction,
        }


