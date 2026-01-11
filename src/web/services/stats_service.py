"""
Stats service for querying count events.

Reads from the count_events table (gate-first schema).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class StatsService:
    """Service for computing statistics from count_events."""
    
    db_path: str
    direction_labels: Optional[Dict[str, str]] = None

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics.
        
        Returns:
            Dict with total_detections, last_hour, last_24h, last_24h_by_direction.
        """
        now = time.time()
        last_hour_start_ms = int((now - 3600) * 1000)
        last_24h_start_ms = int((now - 86400) * 1000)

        try:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                cur = conn.cursor()
                
                # Total count (last 24h by default for "total")
                cur.execute(
                    "SELECT COUNT(*) FROM count_events WHERE ts >= ?",
                    (last_24h_start_ms,)
                )
                total = int(cur.fetchone()[0] or 0)

                # Last hour
                cur.execute(
                    "SELECT COUNT(*) FROM count_events WHERE ts >= ?",
                    (last_hour_start_ms,),
                )
                last_hour = int(cur.fetchone()[0] or 0)

                # Last 24h (same as total in this case)
                last_24h = total

                # By direction (last 24h)
                cur.execute(
                    "SELECT direction_code, COUNT(*) FROM count_events WHERE ts >= ? GROUP BY direction_code",
                    (last_24h_start_ms,),
                )
                raw_dir = {row[0] or "unknown": int(row[1]) for row in cur.fetchall()}

        except sqlite3.Error:
            # If table doesn't exist or other error, return zeros
            return {
                "total_detections": 0,
                "last_hour": 0,
                "last_24h": 0,
                "last_24h_by_direction": {},
            }

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
    
    def get_counts_by_class(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Get count statistics broken down by object class.
        
        Enables modal split analysis (vehicles vs pedestrians vs cyclists).
        Returns counts grouped by class_name and direction.
        
        Args:
            start_time: Start time as Unix timestamp (default: 24 hours ago).
            end_time: End time as Unix timestamp (default: now).
        
        Returns:
            Dict with:
            - by_class: {"car": 120, "bicycle": 15, "person": 8, ...}
            - by_class_and_direction: {"car": {"A_TO_B": 65, "B_TO_A": 55}, ...}
            - total: total count in time range
            - unclassified: count of detections with class_name=NULL (from bgsub)
        """
        now = time.time()
        if start_time is None:
            start_time = now - 86400  # 24 hours ago
        if end_time is None:
            end_time = now
        
        start_ms = int(start_time * 1000)
        end_ms = int(end_time * 1000)
        
        try:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                cur = conn.cursor()
                
                # Total count
                cur.execute(
                    "SELECT COUNT(*) FROM count_events WHERE ts BETWEEN ? AND ?",
                    (start_ms, end_ms)
                )
                total = int(cur.fetchone()[0] or 0)
                
                # Counts by class (NULL class_name grouped as "unclassified")
                cur.execute("""
                    SELECT 
                        COALESCE(class_name, 'unclassified') as class,
                        COUNT(*) as count
                    FROM count_events
                    WHERE ts BETWEEN ? AND ?
                    GROUP BY class
                    ORDER BY count DESC
                """, (start_ms, end_ms))
                by_class = {row[0]: int(row[1]) for row in cur.fetchall()}
                
                # Counts by class and direction
                cur.execute("""
                    SELECT 
                        COALESCE(class_name, 'unclassified') as class,
                        direction_code,
                        COUNT(*) as count
                    FROM count_events
                    WHERE ts BETWEEN ? AND ?
                    GROUP BY class, direction_code
                    ORDER BY class, direction_code
                """, (start_ms, end_ms))
                
                by_class_and_direction = {}
                for row in cur.fetchall():
                    class_name = row[0]
                    direction_code = row[1]
                    count = int(row[2])
                    
                    if class_name not in by_class_and_direction:
                        by_class_and_direction[class_name] = {}
                    by_class_and_direction[class_name][direction_code] = count
                
                # Count unclassified (from bgsub)
                unclassified = by_class.get("unclassified", 0)
                
                return {
                    "total": total,
                    "by_class": by_class,
                    "by_class_and_direction": by_class_and_direction,
                    "unclassified": unclassified,
                    "time_range": {
                        "start": start_time,
                        "end": end_time,
                    }
                }
                
        except sqlite3.Error as e:
            # If table doesn't exist or other error, return empty
            return {
                "total": 0,
                "by_class": {},
                "by_class_and_direction": {},
                "unclassified": 0,
                "time_range": {
                    "start": start_time,
                    "end": end_time,
                },
                "error": str(e),
            }