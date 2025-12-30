"""
Database module for storing traffic monitoring count events.

This module uses a gate-first schema optimized for GateCounter output.
Schema versioning ensures automatic migration when schema changes.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from models.count_event import CountEvent

# Schema version - increment when schema changes
EXPECTED_SCHEMA_VERSION = 1


class Database:
    """
    Database for storing count events from traffic monitoring.
    
    Uses a simplified gate-first schema:
    - schema_meta: tracks schema version
    - count_events: stores individual count events from GateCounter
    
    No backward compatibility with old tables - they are dropped on init.
    """
    
    def __init__(self, local_database_path: str, cloud_enabled: bool = True):
        """
        Initialize the database.
        
        Args:
            local_database_path: Path to the SQLite database file.
            cloud_enabled: Whether cloud sync is enabled (for future use).
        """
        self.local_database_path = local_database_path
        self.cloud_enabled = cloud_enabled
        self.conn: Optional[sqlite3.Connection] = None
        
        # Create directory if it doesn't exist
        db_dir = os.path.dirname(local_database_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        logging.info(f"Database initialized at {local_database_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.local_database_path)
        return self.conn
    
    def _get_schema_version(self) -> Optional[int]:
        """Get current schema version from database."""
        try:
            cursor = self._get_connection().cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
            )
            if cursor.fetchone() is None:
                return None
            
            cursor.execute("SELECT schema_version FROM schema_meta LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else None
        except sqlite3.Error:
            return None
    
    def _drop_old_tables(self) -> None:
        """Drop all old count-related tables."""
        cursor = self._get_connection().cursor()
        
        # List of old tables to drop
        old_tables = [
            "vehicle_detections",
            "hourly_counts", 
            "daily_counts",
            "count_events",  # Drop existing count_events too for clean slate
            "schema_meta",
        ]
        
        for table in old_tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logging.debug(f"Dropped table: {table}")
            except sqlite3.Error as e:
                logging.warning(f"Could not drop table {table}: {e}")
        
        self._get_connection().commit()
        logging.info("Old tables dropped")
    
    def _create_schema(self) -> None:
        """Create the new gate-first schema."""
        cursor = self._get_connection().cursor()
        
        # Create schema_meta table
        cursor.execute("""
            CREATE TABLE schema_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                schema_version INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        
        # Create count_events table (gate-first schema)
        cursor.execute("""
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
                cloud_synced INTEGER DEFAULT 0
            )
        """)
        
        # Create indexes for common queries
        cursor.execute(
            "CREATE INDEX idx_count_events_ts ON count_events(ts)"
        )
        cursor.execute(
            "CREATE INDEX idx_count_events_direction ON count_events(direction_code)"
        )
        cursor.execute(
            "CREATE INDEX idx_count_events_cloud_synced ON count_events(cloud_synced)"
        )
        
        # Insert schema version
        cursor.execute(
            "INSERT INTO schema_meta (id, schema_version) VALUES (1, ?)",
            (EXPECTED_SCHEMA_VERSION,)
        )
        
        self._get_connection().commit()
        logging.info(f"Created schema version {EXPECTED_SCHEMA_VERSION}")
    
    def initialize(self) -> None:
        """
        Initialize the database schema.
        
        If schema_meta is missing or version doesn't match EXPECTED_SCHEMA_VERSION,
        drops all old tables and creates fresh schema.
        """
        try:
            conn = self._get_connection()
            
            current_version = self._get_schema_version()
            
            if current_version != EXPECTED_SCHEMA_VERSION:
                if current_version is not None:
                    logging.warning(
                        f"Schema version mismatch: found {current_version}, "
                        f"expected {EXPECTED_SCHEMA_VERSION}. Dropping old tables."
                    )
                else:
                    logging.info("No schema found, creating fresh database.")
                
                self._drop_old_tables()
                self._create_schema()
            else:
                logging.info(f"Schema version {current_version} is current")
            
        except sqlite3.Error as e:
            logging.error(f"Database initialization error: {e}")
            raise
    
    # -------------------------------------------------------------------------
    # Write Operations
    # -------------------------------------------------------------------------
    
    def add_count_event(self, event: CountEvent) -> Optional[int]:
        """
        Add a count event to the database.
        
        Args:
            event: CountEvent from the counter.
            
        Returns:
            ID of the inserted record, or None on error.
        """
        try:
            cursor = self._get_connection().cursor()
            
            # Convert timestamp to epoch milliseconds
            ts_ms = int(event.timestamp * 1000)
            
            # Determine gate sequence from direction
            if event.gate_sequence:
                gate_seq = event.gate_sequence.replace("_TO_", ",").replace("A,B", "A,B").replace("B,A", "B,A")
                if event.direction == "A_TO_B":
                    gate_seq = "A,B"
                elif event.direction == "B_TO_A":
                    gate_seq = "B,A"
                else:
                    gate_seq = event.gate_sequence
            else:
                gate_seq = None
            
            cursor.execute("""
                INSERT INTO count_events (
                    ts, frame_idx, track_id, direction_code, direction_label,
                    gate_sequence, line_a_cross_frame, line_b_cross_frame,
                    track_age_frames, track_displacement_px, cloud_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                ts_ms,
                event.line_a_cross_frame,  # Use line_a_cross_frame as frame_idx proxy
                event.track_id,
                event.direction,
                event.direction_label,
                gate_seq,
                event.line_a_cross_frame,
                event.line_b_cross_frame,
                event.track_age_frames,
                event.track_displacement_px,
            ))
            
            self._get_connection().commit()
            
            logging.debug(
                f"Count event added: track={event.track_id}, "
                f"direction={event.direction}"
            )
            return cursor.lastrowid
            
        except sqlite3.Error as e:
            logging.error(f"Error adding count event: {e}")
            return None
    
    def add_vehicle_detection(
        self, 
        timestamp: float, 
        direction: str = "unknown",
        direction_label: Optional[str] = None,
    ) -> Optional[int]:
        """
        Legacy method for backward compatibility.
        
        Creates a minimal CountEvent and inserts it.
        Prefer add_count_event() for new code.
        """
        # Create a minimal count event
        event = CountEvent(
            track_id=-1,  # Unknown track
            direction=direction,
            direction_label=direction_label or direction,
            timestamp=timestamp,
            counting_mode="legacy",
            gate_sequence=None,
            line_a_cross_frame=None,
            line_b_cross_frame=None,
            track_age_frames=0,
            track_displacement_px=0.0,
        )
        return self.add_count_event(event)
    
    # -------------------------------------------------------------------------
    # Read Operations - Stats
    # -------------------------------------------------------------------------
    
    def get_count_total(
        self, 
        start_time: Optional[float] = None, 
        end_time: Optional[float] = None,
    ) -> int:
        """
        Get total count of events in a time range.
        
        Args:
            start_time: Start time as Unix timestamp (default: 24 hours ago).
            end_time: End time as Unix timestamp (default: now).
            
        Returns:
            Total count of events.
        """
        try:
            cursor = self._get_connection().cursor()
            
            if start_time is None:
                start_time = time.time() - 86400
            if end_time is None:
                end_time = time.time()
            
            # Convert to milliseconds
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            
            cursor.execute(
                "SELECT COUNT(*) FROM count_events WHERE ts BETWEEN ? AND ?",
                (start_ms, end_ms)
            )
            
            return cursor.fetchone()[0]
            
        except sqlite3.Error as e:
            logging.error(f"Error getting count total: {e}")
            return 0
    
    def get_counts_by_direction_code(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> Dict[str, int]:
        """
        Get counts grouped by direction_code (A_TO_B, B_TO_A).
        
        Args:
            start_time: Start time as Unix timestamp (default: 24 hours ago).
            end_time: End time as Unix timestamp (default: now).
            
        Returns:
            Dict mapping direction_code -> count.
        """
        try:
            cursor = self._get_connection().cursor()
            
            if start_time is None:
                start_time = time.time() - 86400
            if end_time is None:
                end_time = time.time()
            
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            
            cursor.execute("""
                SELECT direction_code, COUNT(*) 
                FROM count_events 
                WHERE ts BETWEEN ? AND ?
                GROUP BY direction_code
            """, (start_ms, end_ms))
            
            return {row[0]: row[1] for row in cursor.fetchall()}
            
        except sqlite3.Error as e:
            logging.error(f"Error getting counts by direction code: {e}")
            return {}
    
    def get_counts_by_direction_label(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> Dict[str, int]:
        """
        Get counts grouped by direction_label (from config).
        
        Args:
            start_time: Start time as Unix timestamp (default: 24 hours ago).
            end_time: End time as Unix timestamp (default: now).
            
        Returns:
            Dict mapping direction_label -> count.
        """
        try:
            cursor = self._get_connection().cursor()
            
            if start_time is None:
                start_time = time.time() - 86400
            if end_time is None:
                end_time = time.time()
            
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            
            cursor.execute("""
                SELECT COALESCE(direction_label, direction_code) as label, COUNT(*) 
                FROM count_events 
                WHERE ts BETWEEN ? AND ?
                GROUP BY label
            """, (start_ms, end_ms))
            
            return {row[0]: row[1] for row in cursor.fetchall()}
            
        except sqlite3.Error as e:
            logging.error(f"Error getting counts by direction label: {e}")
            return {}
    
    # Legacy aliases for backward compatibility
    def get_vehicle_count(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> int:
        """Legacy alias for get_count_total()."""
        return self.get_count_total(start_time, end_time)
    
    def get_direction_counts(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> Dict[str, int]:
        """Legacy alias for get_counts_by_direction_label()."""
        return self.get_counts_by_direction_label(start_time, end_time)
    
    # -------------------------------------------------------------------------
    # Read Operations - Raw Events
    # -------------------------------------------------------------------------
    
    def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get most recent count events.
        
        Args:
            limit: Maximum number of events to return.
            
        Returns:
            List of event dictionaries.
        """
        try:
            self._get_connection().row_factory = sqlite3.Row
            cursor = self._get_connection().cursor()
            
            cursor.execute("""
                SELECT * FROM count_events
                ORDER BY ts DESC
                LIMIT ?
            """, (limit,))
            
            events = [dict(row) for row in cursor.fetchall()]
            
            # Convert ts from ms to seconds for consistency
            for event in events:
                event["timestamp"] = event["ts"] / 1000.0
            
            return events
            
        except sqlite3.Error as e:
            logging.error(f"Error getting recent events: {e}")
            return []
        finally:
            if self.conn:
                self.conn.row_factory = None
    
    def get_unsynced_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get events that haven't been synced to cloud.
        
        Args:
            limit: Maximum number of events to return.
            
        Returns:
            List of event dictionaries.
        """
        try:
            self._get_connection().row_factory = sqlite3.Row
            cursor = self._get_connection().cursor()
            
            cursor.execute("""
                SELECT * FROM count_events
                WHERE cloud_synced = 0
                ORDER BY id
                LIMIT ?
            """, (limit,))
            
            events = [dict(row) for row in cursor.fetchall()]
            
            # Convert ts from ms to seconds
            for event in events:
                event["timestamp"] = event["ts"] / 1000.0
            
            return events
            
        except sqlite3.Error as e:
            logging.error(f"Error getting unsynced events: {e}")
            return []
        finally:
            if self.conn:
                self.conn.row_factory = None
    
    # Legacy alias
    def get_unsynced_detections(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Legacy alias for get_unsynced_events()."""
        return self.get_unsynced_events(limit)
    
    def mark_events_synced(self, ids: List[int]) -> None:
        """
        Mark events as synced to cloud.
        
        Args:
            ids: List of event IDs to mark as synced.
        """
        if not ids:
            return
        
        try:
            cursor = self._get_connection().cursor()
            
            placeholders = ",".join("?" for _ in ids)
            cursor.execute(
                f"UPDATE count_events SET cloud_synced = 1 WHERE id IN ({placeholders})",
                ids
            )
            
            self._get_connection().commit()
            logging.info(f"Marked {len(ids)} events as synced")
            
        except sqlite3.Error as e:
            logging.error(f"Error marking events as synced: {e}")
    
    # Legacy alias
    def mark_detections_synced(self, ids: List[int]) -> None:
        """Legacy alias for mark_events_synced()."""
        self.mark_events_synced(ids)
    
    # -------------------------------------------------------------------------
    # Hourly/Daily Aggregates (simplified - computed on-the-fly)
    # -------------------------------------------------------------------------
    
    def get_hourly_counts(self, days: int = 7) -> List[Tuple[str, int]]:
        """
        Get hourly counts for the past N days.
        
        Args:
            days: Number of days to look back.
            
        Returns:
            List of (hour_str, count) tuples.
        """
        try:
            cursor = self._get_connection().cursor()
            
            start_time = time.time() - (days * 86400)
            start_ms = int(start_time * 1000)
            
            # Group by hour using SQLite datetime functions
            cursor.execute("""
                SELECT 
                    strftime('%Y-%m-%d %H:00:00', ts/1000, 'unixepoch', 'localtime') as hour,
                    COUNT(*) as count
                FROM count_events
                WHERE ts >= ?
                GROUP BY hour
                ORDER BY hour
            """, (start_ms,))
            
            return cursor.fetchall()
            
        except sqlite3.Error as e:
            logging.error(f"Error getting hourly counts: {e}")
            return []
    
    def get_daily_counts(self, days: int = 30) -> List[Tuple[str, int]]:
        """
        Get daily counts for the past N days.
        
        Args:
            days: Number of days to look back.
            
        Returns:
            List of (date_str, count) tuples.
        """
        try:
            cursor = self._get_connection().cursor()
            
            start_time = time.time() - (days * 86400)
            start_ms = int(start_time * 1000)
            
            cursor.execute("""
                SELECT 
                    strftime('%Y-%m-%d', ts/1000, 'unixepoch', 'localtime') as date,
                    COUNT(*) as count
                FROM count_events
                WHERE ts >= ?
                GROUP BY date
                ORDER BY date
            """, (start_ms,))
            
            return cursor.fetchall()
            
        except sqlite3.Error as e:
            logging.error(f"Error getting daily counts: {e}")
            return []
    
    # Legacy no-ops (aggregates computed on-the-fly now)
    def update_hourly_counts(self) -> None:
        """No-op: hourly counts are now computed on-the-fly."""
        pass
    
    def update_daily_counts(self) -> None:
        """No-op: daily counts are now computed on-the-fly."""
        pass
    
    # -------------------------------------------------------------------------
    # Maintenance
    # -------------------------------------------------------------------------
    
    def cleanup_old_data(self, retention_days: int = 60) -> None:
        """
        Remove events older than retention period.
        
        Args:
            retention_days: Days to keep data.
        """
        try:
            cursor = self._get_connection().cursor()
            
            cutoff_time = time.time() - (retention_days * 86400)
            cutoff_ms = int(cutoff_time * 1000)
            
            # Only delete if already synced to cloud
            cursor.execute(
                "DELETE FROM count_events WHERE ts < ? AND cloud_synced = 1",
                (cutoff_ms,)
            )
            
            deleted = cursor.rowcount
            self._get_connection().commit()
            
            if deleted > 0:
                logging.info(f"Cleaned up {deleted} events older than {retention_days} days")
                
        except sqlite3.Error as e:
            logging.error(f"Error cleaning up old data: {e}")
    
    def close(self) -> None:
        """Close database connection."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            logging.info("Database connection closed")
