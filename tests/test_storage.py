"""
Tests for storage/database module.

Tests the new gate-first count_events schema and schema versioning.
"""

import os
import sqlite3
import tempfile
import time

import pytest

from storage.database import Database, EXPECTED_SCHEMA_VERSION
from models.count_event import CountEvent


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    yield path
    # Cleanup
    try:
        os.unlink(path)
    except OSError:
        pass


class TestSchemaCreation:
    """Tests for schema creation and versioning."""
    
    def test_creates_schema_meta_table(self, temp_db):
        """Schema meta table is created on init."""
        db = Database(temp_db)
        db.initialize()
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
        )
        assert cursor.fetchone() is not None
        
        conn.close()
        db.close()
    
    def test_creates_count_events_table(self, temp_db):
        """Count events table is created on init."""
        db = Database(temp_db)
        db.initialize()
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='count_events'"
        )
        assert cursor.fetchone() is not None
        
        conn.close()
        db.close()
    
    def test_count_events_has_expected_columns(self, temp_db):
        """Count events table has all expected columns."""
        db = Database(temp_db)
        db.initialize()
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(count_events)")
        columns = {row[1] for row in cursor.fetchall()}
        
        expected_columns = {
            "id", "ts", "frame_idx", "track_id", "direction_code",
            "direction_label", "gate_sequence", "line_a_cross_frame",
            "line_b_cross_frame", "track_age_frames", "track_displacement_px",
            "cloud_synced"
        }
        
        assert columns == expected_columns
        
        conn.close()
        db.close()
    
    def test_schema_version_set_correctly(self, temp_db):
        """Schema version is set to expected value."""
        db = Database(temp_db)
        db.initialize()
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT schema_version FROM schema_meta")
        version = cursor.fetchone()[0]
        
        assert version == EXPECTED_SCHEMA_VERSION
        
        conn.close()
        db.close()
    
    def test_no_old_tables_exist(self, temp_db):
        """Old tables (vehicle_detections, hourly_counts, daily_counts) do not exist."""
        db = Database(temp_db)
        db.initialize()
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        old_tables = ["vehicle_detections", "hourly_counts", "daily_counts"]
        for table in old_tables:
            cursor.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            )
            assert cursor.fetchone() is None, f"Old table {table} should not exist"
        
        conn.close()
        db.close()
    
    def test_reinitialize_same_version_no_drop(self, temp_db):
        """Reinitializing with same version doesn't drop data."""
        db = Database(temp_db)
        db.initialize()
        
        # Add some data
        event = CountEvent(
            track_id=1,
            direction="A_TO_B",
            direction_label="northbound",
            timestamp=time.time(),
            counting_mode="gate",
            gate_sequence="A,B",
            line_a_cross_frame=10,
            line_b_cross_frame=20,
            track_age_frames=15,
            track_displacement_px=100.0,
        )
        db.add_count_event(event)
        
        count_before = db.get_count_total()
        assert count_before == 1
        
        # Reinitialize
        db.close()
        db2 = Database(temp_db)
        db2.initialize()
        
        count_after = db2.get_count_total()
        assert count_after == 1
        
        db2.close()


class TestWriteOperations:
    """Tests for write operations."""
    
    def test_add_count_event(self, temp_db):
        """Can add a count event."""
        db = Database(temp_db)
        db.initialize()
        
        event = CountEvent(
            track_id=42,
            direction="A_TO_B",
            direction_label="northbound",
            timestamp=time.time(),
            counting_mode="gate",
            gate_sequence="A,B",
            line_a_cross_frame=10,
            line_b_cross_frame=20,
            track_age_frames=15,
            track_displacement_px=100.5,
        )
        
        event_id = db.add_count_event(event)
        assert event_id is not None
        assert event_id > 0
        
        db.close()
    
    def test_add_count_event_stores_all_fields(self, temp_db):
        """All CountEvent fields are stored."""
        db = Database(temp_db)
        db.initialize()
        
        ts = time.time()
        event = CountEvent(
            track_id=99,
            direction="B_TO_A",
            direction_label="southbound",
            timestamp=ts,
            counting_mode="gate",
            gate_sequence="B,A",
            line_a_cross_frame=30,
            line_b_cross_frame=25,
            track_age_frames=20,
            track_displacement_px=150.75,
        )
        
        db.add_count_event(event)
        
        # Query directly
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM count_events WHERE track_id = 99")
        row = dict(cursor.fetchone())
        
        assert row["track_id"] == 99
        assert row["direction_code"] == "B_TO_A"
        assert row["direction_label"] == "southbound"
        assert row["gate_sequence"] == "B,A"
        assert row["line_a_cross_frame"] == 30
        assert row["line_b_cross_frame"] == 25
        assert row["track_age_frames"] == 20
        assert abs(row["track_displacement_px"] - 150.75) < 0.01
        
        conn.close()
        db.close()
    
    def test_legacy_add_vehicle_detection(self, temp_db):
        """Legacy method still works."""
        db = Database(temp_db)
        db.initialize()
        
        event_id = db.add_vehicle_detection(
            timestamp=time.time(),
            direction="A_TO_B",
            direction_label="northbound",
        )
        
        assert event_id is not None
        assert db.get_count_total() == 1
        
        db.close()


class TestReadOperations:
    """Tests for read/stats operations."""
    
    def _add_test_events(self, db):
        """Add test events for stats queries."""
        now = time.time()
        
        # Add A_TO_B events
        for i in range(3):
            event = CountEvent(
                track_id=i,
                direction="A_TO_B",
                direction_label="northbound",
                timestamp=now - i * 100,
                counting_mode="gate",
                gate_sequence="A,B",
                line_a_cross_frame=i * 10,
                line_b_cross_frame=i * 10 + 5,
                track_age_frames=10,
                track_displacement_px=50.0,
            )
            db.add_count_event(event)
        
        # Add B_TO_A events
        for i in range(2):
            event = CountEvent(
                track_id=10 + i,
                direction="B_TO_A",
                direction_label="southbound",
                timestamp=now - i * 100,
                counting_mode="gate",
                gate_sequence="B,A",
                line_a_cross_frame=i * 10 + 5,
                line_b_cross_frame=i * 10,
                track_age_frames=10,
                track_displacement_px=50.0,
            )
            db.add_count_event(event)
    
    def test_get_count_total(self, temp_db):
        """get_count_total returns correct count."""
        db = Database(temp_db)
        db.initialize()
        self._add_test_events(db)
        
        total = db.get_count_total()
        assert total == 5  # 3 A_TO_B + 2 B_TO_A
        
        db.close()
    
    def test_get_counts_by_direction_code(self, temp_db):
        """get_counts_by_direction_code returns correct breakdown."""
        db = Database(temp_db)
        db.initialize()
        self._add_test_events(db)
        
        counts = db.get_counts_by_direction_code()
        
        assert counts.get("A_TO_B") == 3
        assert counts.get("B_TO_A") == 2
        
        db.close()
    
    def test_get_counts_by_direction_label(self, temp_db):
        """get_counts_by_direction_label returns correct breakdown."""
        db = Database(temp_db)
        db.initialize()
        self._add_test_events(db)
        
        counts = db.get_counts_by_direction_label()
        
        assert counts.get("northbound") == 3
        assert counts.get("southbound") == 2
        
        db.close()
    
    def test_get_count_total_time_range(self, temp_db):
        """Time range filtering works."""
        db = Database(temp_db)
        db.initialize()
        
        now = time.time()
        
        # Add old event (2 hours ago)
        old_event = CountEvent(
            track_id=1,
            direction="A_TO_B",
            direction_label="northbound",
            timestamp=now - 7200,
            counting_mode="gate",
            gate_sequence="A,B",
            line_a_cross_frame=1,
            line_b_cross_frame=2,
            track_age_frames=5,
            track_displacement_px=30.0,
        )
        db.add_count_event(old_event)
        
        # Add recent event (5 minutes ago)
        recent_event = CountEvent(
            track_id=2,
            direction="A_TO_B",
            direction_label="northbound",
            timestamp=now - 300,
            counting_mode="gate",
            gate_sequence="A,B",
            line_a_cross_frame=10,
            line_b_cross_frame=20,
            track_age_frames=5,
            track_displacement_px=30.0,
        )
        db.add_count_event(recent_event)
        
        # All time
        assert db.get_count_total(start_time=now - 86400) == 2
        
        # Last hour only
        assert db.get_count_total(start_time=now - 3600) == 1
        
        db.close()
    
    def test_get_recent_events(self, temp_db):
        """get_recent_events returns events in descending order."""
        db = Database(temp_db)
        db.initialize()
        self._add_test_events(db)
        
        events = db.get_recent_events(limit=3)
        
        assert len(events) == 3
        # Should be in descending timestamp order
        for i in range(len(events) - 1):
            assert events[i]["timestamp"] >= events[i + 1]["timestamp"]
        
        db.close()
    
    def test_legacy_get_vehicle_count(self, temp_db):
        """Legacy alias works."""
        db = Database(temp_db)
        db.initialize()
        self._add_test_events(db)
        
        # Legacy method
        count = db.get_vehicle_count()
        assert count == 5
        
        db.close()
    
    def test_legacy_get_direction_counts(self, temp_db):
        """Legacy alias works."""
        db = Database(temp_db)
        db.initialize()
        self._add_test_events(db)
        
        # Legacy method returns by label
        counts = db.get_direction_counts()
        assert "northbound" in counts or "southbound" in counts
        
        db.close()


class TestCloudSync:
    """Tests for cloud sync tracking."""
    
    def test_events_start_unsynced(self, temp_db):
        """New events have cloud_synced=0."""
        db = Database(temp_db)
        db.initialize()
        
        event = CountEvent(
            track_id=1,
            direction="A_TO_B",
            direction_label="northbound",
            timestamp=time.time(),
            counting_mode="gate",
            gate_sequence="A,B",
            line_a_cross_frame=10,
            line_b_cross_frame=20,
            track_age_frames=5,
            track_displacement_px=30.0,
        )
        db.add_count_event(event)
        
        unsynced = db.get_unsynced_events()
        assert len(unsynced) == 1
        
        db.close()
    
    def test_mark_events_synced(self, temp_db):
        """Can mark events as synced."""
        db = Database(temp_db)
        db.initialize()
        
        event = CountEvent(
            track_id=1,
            direction="A_TO_B",
            direction_label="northbound",
            timestamp=time.time(),
            counting_mode="gate",
            gate_sequence="A,B",
            line_a_cross_frame=10,
            line_b_cross_frame=20,
            track_age_frames=5,
            track_displacement_px=30.0,
        )
        event_id = db.add_count_event(event)
        
        unsynced_before = db.get_unsynced_events()
        assert len(unsynced_before) == 1
        
        db.mark_events_synced([event_id])
        
        unsynced_after = db.get_unsynced_events()
        assert len(unsynced_after) == 0
        
        db.close()


class TestHourlyDailyCounts:
    """Tests for computed hourly/daily counts."""
    
    def test_get_hourly_counts(self, temp_db):
        """Hourly counts are computed on-the-fly."""
        db = Database(temp_db)
        db.initialize()
        
        now = time.time()
        
        # Add events spread across hours
        for i in range(5):
            event = CountEvent(
                track_id=i,
                direction="A_TO_B",
                direction_label="northbound",
                timestamp=now - i * 1800,  # Every 30 minutes
                counting_mode="gate",
                gate_sequence="A,B",
                line_a_cross_frame=i,
                line_b_cross_frame=i + 5,
                track_age_frames=5,
                track_displacement_px=30.0,
            )
            db.add_count_event(event)
        
        hourly = db.get_hourly_counts(days=1)
        
        # Should have some hourly data
        total = sum(count for _, count in hourly)
        assert total == 5
        
        db.close()
    
    def test_get_daily_counts(self, temp_db):
        """Daily counts are computed on-the-fly."""
        db = Database(temp_db)
        db.initialize()
        
        now = time.time()
        
        # Add events for today
        for i in range(3):
            event = CountEvent(
                track_id=i,
                direction="A_TO_B",
                direction_label="northbound",
                timestamp=now - i * 100,
                counting_mode="gate",
                gate_sequence="A,B",
                line_a_cross_frame=i,
                line_b_cross_frame=i + 5,
                track_age_frames=5,
                track_displacement_px=30.0,
            )
            db.add_count_event(event)
        
        daily = db.get_daily_counts(days=1)
        
        # Should have today's count
        total = sum(count for _, count in daily)
        assert total == 3
        
        db.close()


class TestCleanup:
    """Tests for data cleanup."""
    
    def test_cleanup_old_synced_data(self, temp_db):
        """Cleanup removes old synced data."""
        db = Database(temp_db)
        db.initialize()
        
        now = time.time()
        old_time = now - 100 * 86400  # 100 days ago
        
        # Add old event
        old_event = CountEvent(
            track_id=1,
            direction="A_TO_B",
            direction_label="northbound",
            timestamp=old_time,
            counting_mode="gate",
            gate_sequence="A,B",
            line_a_cross_frame=1,
            line_b_cross_frame=2,
            track_age_frames=5,
            track_displacement_px=30.0,
        )
        old_id = db.add_count_event(old_event)
        
        # Add recent event
        recent_event = CountEvent(
            track_id=2,
            direction="A_TO_B",
            direction_label="northbound",
            timestamp=now,
            counting_mode="gate",
            gate_sequence="A,B",
            line_a_cross_frame=10,
            line_b_cross_frame=20,
            track_age_frames=5,
            track_displacement_px=30.0,
        )
        db.add_count_event(recent_event)
        
        # Mark old one as synced
        db.mark_events_synced([old_id])
        
        assert db.get_count_total(start_time=0) == 2
        
        # Cleanup with 30 day retention
        db.cleanup_old_data(retention_days=30)
        
        # Old synced event should be gone
        assert db.get_count_total(start_time=0) == 1
        
        db.close()

