"""
Cloud synchronization module for uploading data to GCP.
"""

import os
import time
import logging
import json
from datetime import datetime
import sqlite3
import threading

class CloudSync:
    """Synchronizes local data with cloud services."""
    
    def __init__(self, config, database_path):
        """
        Initialize cloud synchronization.
        
        Args:
            config: Cloud configuration dictionary
            database_path: Path to local SQLite database
        """
        self.config = config
        self.database_path = database_path
        self.is_cloud_enabled = False
        
        # Setup sync interval
        self.sync_interval = config['gcp']['sync']['interval_minutes'] * 60
        self.max_retry_attempts = config['gcp']['sync']['max_retry_attempts']
        self.retry_delay = config['gcp']['sync']['retry_delay_seconds']
        self.batch_size = config['gcp']['sync']['batch_size']
        
        # Tracking variables
        self.last_sync_time = 0
        self.last_synced_id = 0
        self._sync_thread = None
        self._stop_sync = False
        
        # Try to initialize cloud clients
        try:
            # Import GCP libraries only if needed
            from google.cloud import storage, bigquery
            from .auth import get_credentials
            
            # Get credentials
            self.credentials = get_credentials(config['gcp']['credentials_file'])
            if self.credentials is None:
                logging.warning("Cloud sync disabled due to missing credentials")
                return
            
            self.project_id = config['gcp']['project_id']
            
            # Initialize GCP clients
            self.storage_client = storage.Client(
                project=self.project_id, 
                credentials=self.credentials
            )
            self.bigquery_client = bigquery.Client(
                project=self.project_id, 
                credentials=self.credentials
            )
            
            # Get cloud storage bucket
            self.bucket = self.storage_client.bucket(
                config['gcp']['storage']['bucket_name']
            )
            
            self.is_cloud_enabled = True
            logging.info("Cloud sync module initialized successfully")
            
            # Ensure BigQuery tables exist
            self._ensure_bigquery_tables()
            
        except Exception as e:
            logging.error(f"Failed to initialize cloud sync: {e}")
            self.is_cloud_enabled = False
    
    def start_sync_thread(self):
        """Start background thread for periodic sync."""
        if not self.is_cloud_enabled:
            logging.warning("Cannot start sync thread: Cloud sync is not enabled")
            return False
            
        if self._sync_thread is None or not self._sync_thread.is_alive():
            self._stop_sync = False
            self._sync_thread = threading.Thread(target=self._sync_worker)
            self._sync_thread.daemon = True
            self._sync_thread.start()
            logging.info("Cloud sync thread started")
            return True
        return False
    
    def stop_sync_thread(self):
        """Stop the background sync thread."""
        self._stop_sync = True
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=10)
            logging.info("Cloud sync thread stopped")
    
    def _ensure_bigquery_tables(self):
        """Ensure BigQuery dataset and tables exist with correct schemas."""
        if not self.is_cloud_enabled:
            return
        
        try:
            from google.cloud import bigquery
            from google.cloud.exceptions import NotFound
            
            dataset_id = self.config['gcp']['bigquery']['dataset_id']
            dataset_ref = self.bigquery_client.dataset(dataset_id)
            
            # Check if dataset exists, create if not
            try:
                self.bigquery_client.get_dataset(dataset_ref)
                logging.info(f"BigQuery dataset '{dataset_id}' exists")
            except NotFound:
                logging.info(f"Creating BigQuery dataset '{dataset_id}'")
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = "US"  # Default location
                dataset = self.bigquery_client.create_dataset(dataset, exists_ok=True)
                logging.info(f"Created BigQuery dataset '{dataset_id}'")
            
            # Define table schemas
            vehicle_detections_schema = [
                bigquery.SchemaField("id", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("timestamp", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("date_time", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("direction", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("direction_label", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("recorded_at", "TIMESTAMP", mode="NULLABLE"),
            ]
            
            hourly_counts_schema = [
                bigquery.SchemaField("id", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("hour_beginning", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("vehicle_count", "INTEGER", mode="REQUIRED"),
            ]
            
            daily_counts_schema = [
                bigquery.SchemaField("id", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("date", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("vehicle_count", "INTEGER", mode="REQUIRED"),
            ]
            
            # Ensure vehicle_detections table exists
            vehicles_table_id = self.config['gcp']['bigquery']['vehicles_table']
            vehicles_table_ref = dataset_ref.table(vehicles_table_id)
            try:
                self.bigquery_client.get_table(vehicles_table_ref)
                logging.info(f"BigQuery table '{vehicles_table_id}' exists")
            except NotFound:
                logging.info(f"Creating BigQuery table '{vehicles_table_id}'")
                table = bigquery.Table(vehicles_table_ref, schema=vehicle_detections_schema)
                table = self.bigquery_client.create_table(table)
                logging.info(f"Created BigQuery table '{vehicles_table_id}'")
            
            # Ensure hourly_counts table exists
            hourly_table_id = self.config['gcp']['bigquery']['hourly_table']
            hourly_table_ref = dataset_ref.table(hourly_table_id)
            try:
                self.bigquery_client.get_table(hourly_table_ref)
                logging.info(f"BigQuery table '{hourly_table_id}' exists")
            except NotFound:
                logging.info(f"Creating BigQuery table '{hourly_table_id}'")
                table = bigquery.Table(hourly_table_ref, schema=hourly_counts_schema)
                table = self.bigquery_client.create_table(table)
                logging.info(f"Created BigQuery table '{hourly_table_id}'")
            
            # Ensure daily_counts table exists
            daily_table_id = self.config['gcp']['bigquery']['daily_table']
            daily_table_ref = dataset_ref.table(daily_table_id)
            try:
                self.bigquery_client.get_table(daily_table_ref)
                logging.info(f"BigQuery table '{daily_table_id}' exists")
            except NotFound:
                logging.info(f"Creating BigQuery table '{daily_table_id}'")
                table = bigquery.Table(daily_table_ref, schema=daily_counts_schema)
                table = self.bigquery_client.create_table(table)
                logging.info(f"Created BigQuery table '{daily_table_id}'")
        
        except Exception as e:
            logging.error(f"Error ensuring BigQuery tables: {e}")
            # Don't disable cloud sync, but log the error
            logging.warning("Continuing with cloud sync, but tables may not exist")
    
    def _sync_worker(self):
        """Background worker for periodic syncing."""
        while not self._stop_sync:
            try:
                # Check if it's time to sync
                current_time = time.time()
                if current_time - self.last_sync_time >= self.sync_interval:
                    self.sync_data()
                    self.last_sync_time = current_time
            except Exception as e:
                logging.error(f"Error in sync worker: {e}")
            
            # Sleep before next check
            time.sleep(60)  # Check every minute
    
    def sync_data(self):
        """
        Synchronize local data with cloud services with retry logic.
        
        Returns:
            True if sync succeeded, False otherwise
        """
        if not self.is_cloud_enabled:
            logging.warning("Cannot sync data: Cloud sync is not enabled")
            return False
            
        logging.info("Starting data synchronization with cloud")
        
        # Retry sync with exponential backoff
        for attempt in range(self.max_retry_attempts):
            try:
                # Sync vehicle detections
                self._sync_vehicle_detections()
                
                # Sync aggregated counts
                self._sync_hourly_counts()
                self._sync_daily_counts()
                
                logging.info("Data synchronization completed successfully")
                return True
            
            except Exception as e:
                if attempt < self.max_retry_attempts - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logging.warning(f"Synchronization error (attempt {attempt + 1}/{self.max_retry_attempts}): {e}")
                    logging.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logging.error(f"Synchronization failed after {self.max_retry_attempts} attempts: {e}")
                    return False
        
        return False
    
    def _sync_vehicle_detections(self):
        """Sync count events (vehicle detections) to BigQuery."""
        try:
            # Connect to local database
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if count_events table exists (new schema)
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='count_events'"
            )
            if cursor.fetchone() is None:
                logging.info("No count_events table found - skipping sync")
                return
            
            # Get unsynchronized records from new count_events table
            cursor.execute(
                '''
                SELECT * FROM count_events 
                WHERE cloud_synced = 0
                ORDER BY id 
                LIMIT ?
                ''',
                (self.batch_size,)
            )
            
            records = cursor.fetchall()
            if not records:
                logging.info("No new count events to sync")
                return
            
            logging.info(f"Syncing {len(records)} count event records")
            
            # Prepare data for BigQuery (map count_events to vehicle_detections schema)
            rows_to_insert = []
            record_ids = []
            
            for record in records:
                row = dict(record)
                record_ids.append(row['id'])
                
                # Map count_events fields to BigQuery vehicle_detections schema
                ts_seconds = row['ts'] / 1000.0 if row.get('ts') else time.time()
                bq_row = {
                    'id': row['id'],
                    'timestamp': ts_seconds,
                    'date_time': datetime.fromtimestamp(ts_seconds).isoformat(),
                    'direction': row.get('direction_code', 'unknown'),
                    'direction_label': row.get('direction_label'),
                    'recorded_at': datetime.utcnow().isoformat(),
                }
                
                # Remove direction_label if BigQuery table doesn't have it
                if 'direction_label' in bq_row and bq_row['direction_label'] is None:
                    del bq_row['direction_label']
                
                # Validate data before adding
                if self._validate_vehicle_detection(bq_row):
                    rows_to_insert.append(bq_row)
                else:
                    logging.warning(f"Skipping invalid count event record {row.get('id')}")
                    continue
            
            if not rows_to_insert:
                logging.info("No valid count events to sync after validation")
                # Mark records as synced even if invalid to avoid retrying
                if record_ids:
                    placeholders = ','.join(['?' for _ in record_ids])
                    cursor.execute(
                        f"UPDATE count_events SET cloud_synced = 1 WHERE id IN ({placeholders})",
                        record_ids
                    )
                    conn.commit()
                return
            
            # Get BigQuery table reference
            dataset_id = self.config['gcp']['bigquery']['dataset_id']
            table_id = self.config['gcp']['bigquery']['vehicles_table']
            table_ref = f"{self.project_id}.{dataset_id}.{table_id}"
            
            # Insert data to BigQuery
            errors = self.bigquery_client.insert_rows_json(table_ref, rows_to_insert)
            if errors:
                logging.error(f"BigQuery insertion errors: {errors}")
                raise Exception("Failed to insert data into BigQuery")
            
            # Mark records as synced in count_events table
            placeholders = ','.join(['?' for _ in record_ids])
            cursor.execute(
                f"UPDATE count_events SET cloud_synced = 1 WHERE id IN ({placeholders})",
                record_ids
            )
            conn.commit()
            
            logging.info(f"Successfully synced {len(records)} count events")
        
        except Exception as e:
            logging.error(f"Error syncing count events: {e}")
            raise
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _sync_hourly_counts(self):
        """
        Sync hourly counts to BigQuery.
        
        Note: hourly_counts table no longer exists. Hourly aggregates are now
        computed on-the-fly from count_events. This method is a no-op but kept
        for backward compatibility with the sync workflow.
        """
        # Hourly counts are computed on-the-fly from count_events
        # No separate table to sync
        logging.debug("Hourly counts sync skipped - computed on-the-fly from count_events")
    
    def _sync_daily_counts(self):
        """
        Sync daily counts to BigQuery.
        
        Note: daily_counts table no longer exists. Daily aggregates are now
        computed on-the-fly from count_events. This method is a no-op but kept
        for backward compatibility with the sync workflow.
        """
        # Daily counts are computed on-the-fly from count_events
        # No separate table to sync
        logging.debug("Daily counts sync skipped - computed on-the-fly from count_events")
    
    def upload_video_sample(self, video_path, metadata=None):
        """
        Upload a video sample to Cloud Storage.
        
        Args:
            video_path: Path to the local video file
            metadata: Optional dictionary of metadata
        
        Returns:
            URL of the uploaded video or None if upload failed
        """
        if not self.is_cloud_enabled:
            logging.warning("Cannot upload video: Cloud sync is not enabled")
            return None
            
        try:
            # Create a unique blob name
            filename = os.path.basename(video_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            blob_name = f"{self.config['gcp']['storage']['video_samples_folder']}/{timestamp}_{filename}"
            
            # Get blob
            blob = self.bucket.blob(blob_name)
            
            # Set metadata if provided
            if metadata:
                blob.metadata = metadata
            
            # Upload file
            blob.upload_from_filename(video_path)
            
            logging.info(f"Uploaded video sample: {blob_name}")
            
            # Return URL
            return f"gs://{self.bucket.name}/{blob_name}"
        
        except Exception as e:
            logging.error(f"Error uploading video sample: {e}")
            for attempt in range(self.max_retry_attempts):
                try:
                    logging.info(f"Retrying upload (attempt {attempt+1}/{self.max_retry_attempts})")
                    time.sleep(self.retry_delay)
                    
                    # Get new blob reference
                    blob = self.bucket.blob(blob_name)
                    blob.upload_from_filename(video_path)
                    
                    logging.info(f"Retry successful: {blob_name}")
                    return f"gs://{self.bucket.name}/{blob_name}"
                
                except Exception as retry_error:
                    logging.error(f"Retry failed: {retry_error}")
            
            return None
    
    def _validate_vehicle_detection(self, row: dict) -> bool:
        """
        Validate a vehicle detection record before syncing to BigQuery.
        
        Args:
            row: Dictionary containing vehicle detection data
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            required_fields = ['id', 'timestamp', 'date_time']
            for field in required_fields:
                if field not in row:
                    logging.warning(f"Missing required field '{field}' in vehicle detection")
                    return False
            
            # Validate timestamp (should be a positive number)
            timestamp = row.get('timestamp')
            if not isinstance(timestamp, (int, float)) or timestamp <= 0:
                logging.warning(f"Invalid timestamp: {timestamp}")
                return False
            
            # Validate date_time format (basic check)
            date_time = row.get('date_time')
            if not isinstance(date_time, str) or len(date_time) < 10:
                logging.warning(f"Invalid date_time format: {date_time}")
                return False
            
            # Validate direction if present (accept legacy and gate-based values)
            direction = row.get('direction')
            valid_directions = [
                'northbound', 'southbound', 'unknown',  # legacy
                'A_TO_B', 'B_TO_A',  # gate-based raw directions
            ]
            if direction is not None and direction not in valid_directions:
                logging.warning(f"Invalid direction: {direction}")
                return False
            
            return True
        
        except Exception as e:
            logging.error(f"Error validating vehicle detection: {e}")
            return False
    
    def _validate_hourly_count(self, row: dict) -> bool:
        """
        Validate an hourly count record before syncing to BigQuery.
        
        Args:
            row: Dictionary containing hourly count data
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            required_fields = ['id', 'hour_beginning', 'vehicle_count']
            for field in required_fields:
                if field not in row:
                    logging.warning(f"Missing required field '{field}' in hourly count")
                    return False
            
            # Validate vehicle_count (should be non-negative integer)
            vehicle_count = row.get('vehicle_count')
            if not isinstance(vehicle_count, int) or vehicle_count < 0:
                logging.warning(f"Invalid vehicle_count: {vehicle_count}")
                return False
            
            return True
        
        except Exception as e:
            logging.error(f"Error validating hourly count: {e}")
            return False
    
    def _validate_daily_count(self, row: dict) -> bool:
        """
        Validate a daily count record before syncing to BigQuery.
        
        Args:
            row: Dictionary containing daily count data
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            required_fields = ['id', 'date', 'vehicle_count']
            for field in required_fields:
                if field not in row:
                    logging.warning(f"Missing required field '{field}' in daily count")
                    return False
            
            # Validate vehicle_count (should be non-negative integer)
            vehicle_count = row.get('vehicle_count')
            if not isinstance(vehicle_count, int) or vehicle_count < 0:
                logging.warning(f"Invalid vehicle_count: {vehicle_count}")
                return False
            
            # Validate date format (basic check - should be YYYY-MM-DD)
            date = row.get('date')
            if not isinstance(date, str) or len(date) != 10:
                logging.warning(f"Invalid date format: {date}")
                return False
            
            return True
        
        except Exception as e:
            logging.error(f"Error validating daily count: {e}")
            return False