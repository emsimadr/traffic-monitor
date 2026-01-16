#!/usr/bin/env python3
"""
BigQuery Schema Migration: Schema v3
=====================================

Adds schema v3 columns to existing BigQuery vehicle_detections table:
- class_id (INTEGER) - YOLO class ID
- class_name (STRING) - Human-readable class name (car, person, etc.)
- confidence (FLOAT) - Detection confidence score (0.0-1.0)
- detection_backend (STRING) - Backend used (yolo, bgsub, hailo)
- platform (STRING) - Operating system and version
- process_pid (INTEGER) - Process ID that made the detection

Usage:
    python tools/migrate_bigquery_schema_v3.py [--dry-run] [--config path/to/cloud_config.yaml]

Options:
    --dry-run    Show what would be changed without making changes
    --config     Path to cloud config file (default: config/cloud_config.yaml)

Requirements:
    - BigQuery tables.update permission
    - Valid GCP credentials configured
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml
from google.cloud import bigquery
from google.cloud.exceptions import NotFound


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


SCHEMA_V3_COLUMNS = [
    ("class_id", "INTEGER", "NULLABLE", "YOLO class ID"),
    ("class_name", "STRING", "NULLABLE", "Human-readable class name"),
    ("confidence", "FLOAT", "NULLABLE", "Detection confidence score (0.0-1.0)"),
    ("detection_backend", "STRING", "NULLABLE", "Detection backend (yolo, bgsub, hailo)"),
    ("platform", "STRING", "NULLABLE", "Operating system and version"),
    ("process_pid", "INTEGER", "NULLABLE", "Process ID that made the detection"),
]


def load_config(config_path: str) -> dict:
    """Load cloud configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def check_table_schema(client: bigquery.Client, table_ref) -> dict:
    """Get current table schema and identify missing columns."""
    try:
        table = client.get_table(table_ref)
        current_fields = {field.name: field for field in table.schema}
        
        missing_columns = []
        for col_name, col_type, col_mode, col_desc in SCHEMA_V3_COLUMNS:
            if col_name not in current_fields:
                missing_columns.append((col_name, col_type, col_mode, col_desc))
        
        return {
            'exists': True,
            'current_schema': table.schema,
            'missing_columns': missing_columns,
        }
    except NotFound:
        return {
            'exists': False,
            'current_schema': None,
            'missing_columns': SCHEMA_V3_COLUMNS,
        }


def update_table_schema(client: bigquery.Client, table_ref, missing_columns: list, dry_run: bool = False):
    """Add missing columns to the table."""
    if not missing_columns:
        logging.info("✅ Table schema is already up to date")
        return True
    
    logging.info(f"📊 Adding {len(missing_columns)} missing columns:")
    for col_name, col_type, col_mode, col_desc in missing_columns:
        logging.info(f"   - {col_name} ({col_type}, {col_mode}): {col_desc}")
    
    if dry_run:
        logging.info("🔍 DRY RUN: Would add these columns (not actually updating)")
        return True
    
    try:
        # Get current table
        table = client.get_table(table_ref)
        
        # Add missing fields
        new_fields = []
        for col_name, col_type, col_mode, col_desc in missing_columns:
            new_fields.append(
                bigquery.SchemaField(col_name, col_type, mode=col_mode, description=col_desc)
            )
        
        # Update schema
        table.schema = list(table.schema) + new_fields
        table = client.update_table(table, ["schema"])
        
        logging.info("✅ Successfully updated table schema")
        return True
        
    except Exception as e:
        logging.error(f"❌ Error updating table schema: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Migrate BigQuery vehicle_detections table to schema v3"
    )
    parser.add_argument(
        "--config",
        default="config/cloud_config.yaml",
        help="Path to cloud config file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes"
    )
    args = parser.parse_args()
    
    logging.info("=" * 60)
    logging.info("BigQuery Schema Migration: Schema v3")
    logging.info("=" * 60)
    
    # Load configuration
    logging.info(f"Loading configuration from {args.config}")
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        logging.error(f"❌ Config file not found: {args.config}")
        return 1
    except Exception as e:
        logging.error(f"❌ Error loading config: {e}")
        return 1
    
    # Initialize BigQuery client
    logging.info("Initializing BigQuery client")
    try:
        gcp_config = config.get('gcp', {})
        project_id = gcp_config.get('project_id')
        credentials_path = gcp_config.get('credentials_file')
        
        if credentials_path:
            import os
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        
        client = bigquery.Client(project=project_id)
        logging.info(f"✅ Connected to project: {project_id}")
    except Exception as e:
        logging.error(f"❌ Error initializing BigQuery client: {e}")
        return 1
    
    # Get table reference
    try:
        bq_config = gcp_config.get('bigquery', {})
        dataset_id = bq_config.get('dataset_id')
        table_id = bq_config.get('vehicles_table')
        
        table_ref = client.dataset(dataset_id).table(table_id)
        full_table_name = f"{project_id}.{dataset_id}.{table_id}"
        
        logging.info(f"Target table: {full_table_name}")
    except Exception as e:
        logging.error(f"❌ Error getting table reference: {e}")
        return 1
    
    # Check current schema
    logging.info("Checking current table schema...")
    schema_info = check_table_schema(client, table_ref)
    
    if not schema_info['exists']:
        logging.error(f"❌ Table does not exist: {full_table_name}")
        logging.info("💡 Table will be created automatically when CloudSync runs")
        return 1
    
    logging.info(f"✅ Table exists with {len(schema_info['current_schema'])} columns")
    
    if not schema_info['missing_columns']:
        logging.info("🎉 Table schema is already up to date!")
        logging.info("=" * 60)
        return 0
    
    # Update schema
    logging.info("")
    logging.info("=" * 60)
    if args.dry_run:
        logging.info("DRY RUN MODE - No changes will be made")
    else:
        logging.info("UPDATING TABLE SCHEMA")
    logging.info("=" * 60)
    
    success = update_table_schema(
        client,
        table_ref,
        schema_info['missing_columns'],
        dry_run=args.dry_run
    )
    
    logging.info("=" * 60)
    if success:
        if args.dry_run:
            logging.info("✅ Dry run completed successfully")
            logging.info("💡 Run without --dry-run to apply changes")
        else:
            logging.info("✅ Migration completed successfully")
            logging.info("💡 New data will now include schema v3 fields")
        return 0
    else:
        logging.error("❌ Migration failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

