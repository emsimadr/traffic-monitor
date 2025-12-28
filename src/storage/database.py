"""
Database module for storing traffic monitoring data.
For Milestone 1, this implements basic storage of vehicle detections.
"""

import sqlite3
import logging
import os
import time
from datetime import datetime, timedelta

class Database:
    """Database for storing traffic monitoring data."""
    
    def __init__(self, local_database_path, cloud_enabled=True):
        """
        Initialize the database.
        
        Args:
            local_database_path: Path to the SQLite database file
            cloud_enabled: Whether cloud storage is enabled
        """
        self.local_database_path = local_database_path
        self.cloud_enabled = cloud_enabled
        self.conn = None
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(local_database_path), exist_ok=True)
        
        logging.info(f"Database initialized at {local_database_path} (Cloud enabled: {cloud_enabled})")
    
    def initialize(self):
        """Initialize the database schema if it doesn't exist."""
        try:
            self.conn = sqlite3.connect(self.local_database_path)
            cursor = self.conn.cursor()
            
            # Create vehicle_detections table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicle_detections (
                id INTEGER PRIMARY KEY,
                timestamp REAL NOT NULL,
                date_time TEXT NOT NULL,
                direction TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cloud_synced INTEGER DEFAULT 0
            )
            ''')
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_vehicle_detections_ts_dir ON vehicle_detections(timestamp, direction)"
            )
            
            # Create hourly_counts table for aggregated data
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS hourly_counts (
                id INTEGER PRIMARY KEY,
                hour_beginning TIMESTAMP NOT NULL,
                vehicle_count INTEGER NOT NULL,
                cloud_synced INTEGER DEFAULT 0,
                UNIQUE(hour_beginning)
            )
            ''')
            
            # Create daily_counts table for aggregated data
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_counts (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                vehicle_count INTEGER NOT NULL,
                cloud_synced INTEGER DEFAULT 0,
                UNIQUE(date)
            )
            ''')
            
            self.conn.commit()
            logging.info("Database schema initialized")
        except sqlite3.Error as e:
            logging.error(f"Database initialization error: {e}")
            raise
    
    def add_vehicle_detection(self, timestamp, direction="unknown"):
        """
        Add a vehicle detection record.
        
        Args:
            timestamp: Unix timestamp of the detection
            direction: Direction of travel (e.g., "northbound", "southbound")
        
        Returns:
            ID of the inserted record
        """
        try:
            if self.conn is None:
                self.conn = sqlite3.connect(self.local_database_path)
            
            cursor = self.conn.cursor()
            
            # Convert timestamp to human-readable datetime
            dt = datetime.fromtimestamp(timestamp)
            date_time = dt.strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute(
                'INSERT INTO vehicle_detections (timestamp, date_time, direction, cloud_synced) VALUES (?, ?, ?, ?)',
                (timestamp, date_time, direction, 0)
            )
            
            self.conn.commit()
            
            logging.debug(f"Vehicle detection added: {date_time}, {direction}")
            return cursor.lastrowid
        
        except sqlite3.Error as e:
            logging.error(f"Error adding vehicle detection: {e}")
            return None
    
    def get_vehicle_count(self, start_time=None, end_time=None):
        """
        Get the count of vehicles detected in a time range.
        
        Args:
            start_time: Start time as Unix timestamp (default: 24 hours ago)
            end_time: End time as Unix timestamp (default: now)
        
        Returns:
            Count of vehicles
        """
        try:
            if self.conn is None:
                self.conn = sqlite3.connect(self.local_database_path)
            
            cursor = self.conn.cursor()
            
            # Set default time range if not provided
            if start_time is None:
                start_time = time.time() - 86400  # 24 hours ago
            
            if end_time is None:
                end_time = time.time()
            
            # Query the count
            cursor.execute(
                'SELECT COUNT(*) FROM vehicle_detections WHERE timestamp BETWEEN ? AND ?',
                (start_time, end_time)
            )
            
            count = cursor.fetchone()[0]
            return count
        
        except sqlite3.Error as e:
            logging.error(f"Error getting vehicle count: {e}")
            return 0

    def get_direction_counts(self, start_time=None, end_time=None):
        """
        Get vehicle counts grouped by direction for a time range.

        Args:
            start_time: Start time as Unix timestamp (default: 24 hours ago)
            end_time: End time as Unix timestamp (default: now)

        Returns:
            dict mapping direction -> count
        """
        try:
            if self.conn is None:
                self.conn = sqlite3.connect(self.local_database_path)

            cursor = self.conn.cursor()

            if start_time is None:
                start_time = time.time() - 86400
            if end_time is None:
                end_time = time.time()

            cursor.execute(
                "SELECT direction, COUNT(*) FROM vehicle_detections WHERE timestamp BETWEEN ? AND ? GROUP BY direction",
                (start_time, end_time),
            )
            return {row[0] or "unknown": int(row[1]) for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logging.error(f"Error getting direction counts: {e}")
            return {}
    
    def update_hourly_counts(self):
        """
        Update the hourly_counts table with aggregated data.
        This should be called periodically to maintain updated statistics.
        """
        try:
            if self.conn is None:
                self.conn = sqlite3.connect(self.local_database_path)
            
            cursor = self.conn.cursor()
            
            # Get the last hour with data
            cursor.execute('SELECT MAX(hour_beginning) FROM hourly_counts')
            result = cursor.fetchone()
            
            if result[0] is None:
                # No data yet, start from 48 hours ago
                last_hour = datetime.now() - timedelta(hours=48)
                last_hour = last_hour.replace(minute=0, second=0, microsecond=0)
            else:
                last_hour = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
            
            # Get current hour
            current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
            
            # Update hour by hour
            while last_hour < current_hour:
                next_hour = last_hour + timedelta(hours=1)
                
                # Convert to timestamps
                start_timestamp = last_hour.timestamp()
                end_timestamp = next_hour.timestamp()
                
                # Get count for this hour
                cursor.execute(
                    'SELECT COUNT(*) FROM vehicle_detections WHERE timestamp >= ? AND timestamp < ?',
                    (start_timestamp, end_timestamp)
                )
                
                count = cursor.fetchone()[0]
                
                # Insert or update hourly count
                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO hourly_counts (hour_beginning, vehicle_count, cloud_synced)
                    VALUES (?, ?, ?)
                    ''',
                    (last_hour.strftime('%Y-%m-%d %H:%M:%S'), count, 0)
                )
                
                last_hour = next_hour
            
            self.conn.commit()
            logging.info("Hourly counts updated")
        
        except sqlite3.Error as e:
            logging.error(f"Error updating hourly counts: {e}")
    
    def update_daily_counts(self):
        """
        Update the daily_counts table with aggregated data.
        This should be called periodically to maintain updated statistics.
        """
        try:
            if self.conn is None:
                self.conn = sqlite3.connect(self.local_database_path)
            
            cursor = self.conn.cursor()
            
            # Get the last day with data
            cursor.execute('SELECT MAX(date) FROM daily_counts')
            result = cursor.fetchone()
            
            if result[0] is None:
                # No data yet, start from 30 days ago
                last_day = datetime.now() - timedelta(days=30)
                last_day = last_day.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                last_day = datetime.strptime(result[0], '%Y-%m-%d')
                last_day = last_day.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Get current day
            current_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Update day by day
            while last_day < current_day:
                next_day = last_day + timedelta(days=1)
                
                # Convert to timestamps
                start_timestamp = last_day.timestamp()
                end_timestamp = next_day.timestamp()
                
                # Get count for this day
                cursor.execute(
                    'SELECT COUNT(*) FROM vehicle_detections WHERE timestamp >= ? AND timestamp < ?',
                    (start_timestamp, end_timestamp)
                )
                
                count = cursor.fetchone()[0]
                
                # Insert or update daily count
                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO daily_counts (date, vehicle_count, cloud_synced)
                    VALUES (?, ?, ?)
                    ''',
                    (last_day.strftime('%Y-%m-%d'), count, 0)
                )
                
                last_day = next_day
            
            self.conn.commit()
            logging.info("Daily counts updated")
        
        except sqlite3.Error as e:
            logging.error(f"Error updating daily counts: {e}")
    
    def get_hourly_counts(self, days=7):
        """
        Get hourly vehicle counts for the specified number of days.
        
        Args:
            days: Number of days to retrieve data for
        
        Returns:
            List of tuples (hour_beginning, vehicle_count)
        """
        try:
            if self.conn is None:
                self.conn = sqlite3.connect(self.local_database_path)
            
            cursor = self.conn.cursor()
            
            # Calculate start time
            start_time = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            
            # Query hourly counts
            cursor.execute(
                '''
                SELECT hour_beginning, vehicle_count FROM hourly_counts
                WHERE hour_beginning >= ?
                ORDER BY hour_beginning ASC
                ''',
                (start_time,)
            )
            
            return cursor.fetchall()
        
        except sqlite3.Error as e:
            logging.error(f"Error getting hourly counts: {e}")
            return []
    
    def get_daily_counts(self, days=30):
        """
        Get daily vehicle counts for the specified number of days.
        
        Args:
            days: Number of days to retrieve data for
        
        Returns:
            List of tuples (date, vehicle_count)
        """
        try:
            if self.conn is None:
                self.conn = sqlite3.connect(self.local_database_path)
            
            cursor = self.conn.cursor()
            
            # Calculate start date
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Query daily counts
            cursor.execute(
                '''
                SELECT date, vehicle_count FROM daily_counts
                WHERE date >= ?
                ORDER BY date ASC
                ''',
                (start_date,)
            )
            
            return cursor.fetchall()
        
        except sqlite3.Error as e:
            logging.error(f"Error getting daily counts: {e}")
            return []
    
    def get_unsynced_detections(self, limit=100):
        """
        Get vehicle detections that haven't been synced to the cloud.
        
        Args:
            limit: Maximum number of records to return
        
        Returns:
            List of dictionaries with detection data
        """
        try:
            if self.conn is None:
                self.conn = sqlite3.connect(self.local_database_path)
            
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.cursor()
            
            cursor.execute(
                '''
                SELECT * FROM vehicle_detections
                WHERE cloud_synced = 0
                ORDER BY id
                LIMIT ?
                ''',
                (limit,)
            )
            
            return [dict(row) for row in cursor.fetchall()]
        
        except sqlite3.Error as e:
            logging.error(f"Error getting unsynced detections: {e}")
            return []
        finally:
            # Reset row factory
            if self.conn:
                self.conn.row_factory = None
    
    def mark_detections_synced(self, ids):
        """
        Mark vehicle detections as synced to the cloud.
        
        Args:
            ids: List of detection IDs to mark as synced
        """
        if not ids:
            return
            
        try:
            if self.conn is None:
                self.conn = sqlite3.connect(self.local_database_path)
            
            cursor = self.conn.cursor()
            
            # Convert list to comma-separated string for SQL IN clause
            id_string = ','.join('?' for _ in ids)
            
            cursor.execute(
                f'UPDATE vehicle_detections SET cloud_synced = 1 WHERE id IN ({id_string})',
                ids
            )
            
            self.conn.commit()
            logging.info(f"Marked {len(ids)} detections as synced")
        
        except sqlite3.Error as e:
            logging.error(f"Error marking detections as synced: {e}")
    
    def close(self):
        """Close the database connection."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            logging.info("Database connection closed")
    
    def cleanup_old_data(self, retention_days=60):
        """
        Remove data older than the specified retention period.
        
        Args:
            retention_days: Number of days to keep data for
        """
        try:
            if self.conn is None:
                self.conn = sqlite3.connect(self.local_database_path)
            
            cursor = self.conn.cursor()
            
            # Calculate cutoff timestamp
            cutoff_timestamp = (datetime.now() - timedelta(days=retention_days)).timestamp()
            
            # Delete old vehicle detections
            cursor.execute(
                'DELETE FROM vehicle_detections WHERE timestamp < ? AND cloud_synced = 1',
                (cutoff_timestamp,)
            )
            
            deleted_count = cursor.rowcount
            
            # Calculate cutoff date for hourly counts
            cutoff_hour = (datetime.now() - timedelta(days=retention_days)).strftime('%Y-%m-%d %H:%M:%S')
            
            # Delete old hourly counts
            cursor.execute(
                'DELETE FROM hourly_counts WHERE hour_beginning < ? AND cloud_synced = 1',
                (cutoff_hour,)
            )
            
            # Calculate cutoff date for daily counts
            cutoff_day = (datetime.now() - timedelta(days=retention_days)).strftime('%Y-%m-%d')
            
            # Delete old daily counts
            cursor.execute(
                'DELETE FROM daily_counts WHERE date < ? AND cloud_synced = 1',
                (cutoff_day,)
            )
            
            self.conn.commit()
            logging.info(f"Cleaned up {deleted_count} vehicle detections older than {retention_days} days")
        
        except sqlite3.Error as e:
            logging.error(f"Error cleaning up old data: {e}")