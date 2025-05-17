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
        Synchronize local data with cloud services.
        """
        if not self.is_cloud_enabled:
            logging.warning("Cannot sync data: Cloud sync is not enabled")
            return False
            
        logging.info("Starting data synchronization with cloud")
        
        try:
            # Sync vehicle detections
            self._sync_vehicle_detections()
            
            # Sync aggregated counts
            self._sync_hourly_counts()
            self._sync_daily_counts()
            
            logging.info("Data synchronization completed successfully")
            return True
        
        except Exception as e:
            logging.error(f"Synchronization error: {e}")
            return False
    
    def _sync_vehicle_detections(self):
        """Sync vehicle detection data to BigQuery."""
        try:
            # Connect to local database
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get unsynchronized records
            cursor.execute(
                '''
                SELECT * FROM vehicle_detections 
                WHERE cloud_synced = 0
                ORDER BY id 
                LIMIT ?
                ''',
                (self.batch_size,)
            )
            
            records = cursor.fetchall()
            if not records:
                logging.info("No new vehicle detections to sync")
                return
            
            logging.info(f"Syncing {len(records)} vehicle detection records")
            
            # Prepare data for BigQuery
            rows_to_insert = []
            record_ids = []
            
            for record in records:
                row = dict(record)
                record_ids.append(row['id'])
                # Remove SQLite-specific fields
                if 'cloud_synced' in row:
                    del row['cloud_synced']
                rows_to_insert.append(row)
            
            # Get BigQuery table reference
            dataset_id = self.config['gcp']['bigquery']['dataset_id']
            table_id = self.config['gcp']['bigquery']['vehicles_table']
            table_ref = f"{self.project_id}.{dataset_id}.{table_id}"
            
            # Insert data to BigQuery
            errors = self.bigquery_client.insert_rows_json(table_ref, rows_to_insert)
            if errors:
                logging.error(f"BigQuery insertion errors: {errors}")
                raise Exception("Failed to insert data into BigQuery")
            
            # Mark records as synced
            placeholders = ','.join(['?' for _ in record_ids])
            cursor.execute(
                f"UPDATE vehicle_detections SET cloud_synced = 1 WHERE id IN ({placeholders})",
                record_ids
            )
            conn.commit()
            
            logging.info(f"Successfully synced {len(records)} vehicle detections")
        
        except Exception as e:
            logging.error(f"Error syncing vehicle detections: {e}")
            raise
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _sync_hourly_counts(self):
        """Sync hourly counts to BigQuery."""
        try:
            # Connect to local database
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get unsynchronized records
            cursor.execute(
                '''
                SELECT * FROM hourly_counts 
                WHERE cloud_synced = 0
                ORDER BY hour_beginning
                LIMIT ?
                ''',
                (self.batch_size,)
            )
            
            records = cursor.fetchall()
            if not records:
                logging.info("No new hourly counts to sync")
                return
            
            logging.info(f"Syncing {len(records)} hourly count records")
            
            # Prepare data for BigQuery
            rows_to_insert = []
            record_ids = []
            
            for record in records:
                row = dict(record)
                record_ids.append(row['id'])
                # Remove SQLite-specific fields
                if 'cloud_synced' in row:
                    del row['cloud_synced']
                rows_to_insert.append(row)
            
            # Get BigQuery table reference
            dataset_id = self.config['gcp']['bigquery']['dataset_id']
            table_id = self.config['gcp']['bigquery']['hourly_table']
            table_ref = f"{self.project_id}.{dataset_id}.{table_id}"
            
            # Insert data to BigQuery
            errors = self.bigquery_client.insert_rows_json(table_ref, rows_to_insert)
            if errors:
                logging.error(f"BigQuery insertion errors: {errors}")
                raise Exception("Failed to insert hourly counts into BigQuery")
            
            # Mark records as synced
            placeholders = ','.join(['?' for _ in record_ids])
            cursor.execute(
                f"UPDATE hourly_counts SET cloud_synced = 1 WHERE id IN ({placeholders})",
                record_ids
            )
            conn.commit()
            
            logging.info(f"Successfully synced {len(records)} hourly counts")
        
        except Exception as e:
            logging.error(f"Error syncing hourly counts: {e}")
            raise
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _sync_daily_counts(self):
        """Sync daily counts to BigQuery."""
        try:
            # Connect to local database
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get unsynchronized records