import os
import sqlite3
import tempfile
import time

from web.services.stats_service import StatsService


def _init_db(path: str):
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE vehicle_detections (
                id INTEGER PRIMARY KEY,
                timestamp REAL NOT NULL,
                date_time TEXT NOT NULL,
                direction TEXT,
                direction_label TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cloud_synced INTEGER DEFAULT 0
            )
            """
        )
        now = time.time()
        rows = [
            (now - 100, "now-100", "A_TO_B", "north"),
            (now - 50, "now-50", "B_TO_A", "south"),
            (now - 10, "now-10", "A_TO_B", "north"),
        ]
        cur.executemany(
            "INSERT INTO vehicle_detections (timestamp, date_time, direction, direction_label) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()


def test_stats_service_maps_direction_labels():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        _init_db(path)
        svc = StatsService(db_path=path, direction_labels={"a_to_b": "north", "b_to_a": "south"})
        summary = svc.get_summary()
        by_dir = summary["last_24h_by_direction"]
        assert by_dir["north"] == 2
        assert by_dir["south"] == 1
        assert summary["total_detections"] == 3
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


