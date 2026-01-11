import os
import sqlite3
import tempfile
import time

from web.services.stats_service import StatsService


def _init_db(path: str):
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        # Use the new count_events schema that StatsService queries (schema v3 with class fields)
        cur.execute(
            """
            CREATE TABLE count_events (
                id INTEGER PRIMARY KEY,
                ts INTEGER NOT NULL,
                frame_idx INTEGER,
                track_id INTEGER NOT NULL,
                direction_code TEXT NOT NULL,
                direction_label TEXT,
                gate_sequence TEXT,
                line_a_cross_frame INTEGER,
                line_b_cross_frame INTEGER,
                track_age_frames INTEGER,
                track_displacement_px REAL,
                class_id INTEGER,
                class_name TEXT,
                confidence REAL DEFAULT 1.0,
                detection_backend TEXT DEFAULT 'unknown',
                cloud_synced INTEGER DEFAULT 0
            )
            """
        )
        now = time.time()
        # ts is in milliseconds
        rows = [
            (int((now - 100) * 1000), 1, "A_TO_B", "north"),
            (int((now - 50) * 1000), 2, "B_TO_A", "south"),
            (int((now - 10) * 1000), 3, "A_TO_B", "north"),
        ]
        cur.executemany(
            "INSERT INTO count_events (ts, track_id, direction_code, direction_label) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()


def _init_db_with_classes(path: str):
    """Initialize DB with multi-class detection data."""
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE count_events (
                id INTEGER PRIMARY KEY,
                ts INTEGER NOT NULL,
                frame_idx INTEGER,
                track_id INTEGER NOT NULL,
                direction_code TEXT NOT NULL,
                direction_label TEXT,
                gate_sequence TEXT,
                line_a_cross_frame INTEGER,
                line_b_cross_frame INTEGER,
                track_age_frames INTEGER,
                track_displacement_px REAL,
                class_id INTEGER,
                class_name TEXT,
                confidence REAL DEFAULT 1.0,
                detection_backend TEXT DEFAULT 'unknown',
                cloud_synced INTEGER DEFAULT 0
            )
            """
        )
        now = time.time()
        # Mix of classified (YOLO) and unclassified (bgsub) detections
        rows = [
            # YOLO detections (classified)
            (int((now - 100) * 1000), 1, "A_TO_B", "north", 2, "car", 0.95, "yolo"),
            (int((now - 90) * 1000), 2, "B_TO_A", "south", 2, "car", 0.88, "yolo"),
            (int((now - 80) * 1000), 3, "A_TO_B", "north", 2, "car", 0.92, "yolo"),
            (int((now - 70) * 1000), 4, "B_TO_A", "south", 1, "bicycle", 0.85, "yolo"),
            (int((now - 60) * 1000), 5, "A_TO_B", "north", 1, "bicycle", 0.78, "yolo"),
            (int((now - 50) * 1000), 6, "A_TO_B", "north", 0, "person", 0.91, "yolo"),
            (int((now - 40) * 1000), 7, "B_TO_A", "south", 3, "motorcycle", 0.87, "yolo"),
            # Background subtraction detections (unclassified)
            (int((now - 30) * 1000), 8, "A_TO_B", "north", None, None, 1.0, "bgsub"),
            (int((now - 20) * 1000), 9, "B_TO_A", "south", None, None, 1.0, "bgsub"),
            (int((now - 10) * 1000), 10, "A_TO_B", "north", None, None, 1.0, "bgsub"),
        ]
        cur.executemany(
            """INSERT INTO count_events 
               (ts, track_id, direction_code, direction_label, class_id, class_name, confidence, detection_backend) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
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


def test_stats_service_counts_by_class():
    """Test class-based statistics (modal split analytics)."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        _init_db_with_classes(path)
        svc = StatsService(db_path=path, direction_labels={"a_to_b": "north", "b_to_a": "south"})
        
        # Get class breakdown
        result = svc.get_counts_by_class()
        
        # Check total
        assert result["total"] == 10, f"Expected 10 total, got {result['total']}"
        
        # Check by_class counts
        by_class = result["by_class"]
        assert by_class["car"] == 3, f"Expected 3 cars, got {by_class.get('car')}"
        assert by_class["bicycle"] == 2, f"Expected 2 bicycles, got {by_class.get('bicycle')}"
        assert by_class["person"] == 1, f"Expected 1 person, got {by_class.get('person')}"
        assert by_class["motorcycle"] == 1, f"Expected 1 motorcycle, got {by_class.get('motorcycle')}"
        assert by_class["unclassified"] == 3, f"Expected 3 unclassified, got {by_class.get('unclassified')}"
        
        # Check by_class_and_direction
        by_class_dir = result["by_class_and_direction"]
        assert by_class_dir["car"]["A_TO_B"] == 2
        assert by_class_dir["car"]["B_TO_A"] == 1
        assert by_class_dir["bicycle"]["A_TO_B"] == 1  # Track 5
        assert by_class_dir["bicycle"]["B_TO_A"] == 1  # Track 4
        assert by_class_dir["person"]["A_TO_B"] == 1
        
        # Check unclassified count
        assert result["unclassified"] == 3, "Expected 3 unclassified (from bgsub)"
        
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def test_stats_service_counts_by_class_time_range():
    """Test class-based statistics with custom time range."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        _init_db_with_classes(path)
        svc = StatsService(db_path=path)
        
        now = time.time()
        # Only count events from last 55 seconds (should exclude first 5 events at -100, -90, -80, -70, -60)
        result = svc.get_counts_by_class(start_time=now - 55, end_time=now)
        
        # Should have 5 events (from -50s to -10s)
        # Events: -50 (bicycle), -40 (person), -30 (unclassified), -20 (unclassified), -10 (unclassified)
        assert result["total"] == 5, f"Expected 5 events in last 55s, got {result['total']}"
        
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def test_stats_service_counts_by_class_empty_db():
    """Test class-based statistics on empty database."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        # Create empty DB
        with sqlite3.connect(path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE count_events (
                    id INTEGER PRIMARY KEY,
                    ts INTEGER NOT NULL,
                    track_id INTEGER NOT NULL,
                    direction_code TEXT NOT NULL,
                    class_id INTEGER,
                    class_name TEXT
                )
                """
            )
            conn.commit()
        
        svc = StatsService(db_path=path)
        result = svc.get_counts_by_class()
        
        assert result["total"] == 0
        assert result["by_class"] == {}
        assert result["by_class_and_direction"] == {}
        assert result["unclassified"] == 0
        
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


