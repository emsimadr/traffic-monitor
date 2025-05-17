#!/usr/bin/env python3
"""
Test script for cloud connectivity.
This utility helps verify that the cloud connection is working properly.

Usage:
    python tools/test_cloud_connection.py --config config/cloud_config.yaml
"""

import argparse
import os
import sys
import yaml
import logging

# Add project directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cloud.auth import get_credentials
from src.cloud.utils import check_cloud_config

def main():
    """Main function for cloud connectivity testing."""
    parser = argparse.ArgumentParser(description='Test cloud connectivity')
    parser.add_argument('--config', type=str, default='config/cloud_config.yaml',
                       help='Path to cloud configuration file')
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print(f"Testing cloud connectivity with configuration: {args.config}")
    
    # Load configuration
    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"ERROR: Failed to load cloud configuration: {e}")
        return 1
    
    # Validate configuration
    if not check_cloud_config(config):
        print("ERROR: Invalid cloud configuration")
        return 1
    
    print("Cloud configuration is valid")
    
    # Test authentication
    credentials_path = config['gcp']['credentials_file']
    print(f"Testing authentication with credentials: {credentials_path}")
    
    credentials = get_credentials(credentials_path)
    if credentials is None:
        print("ERROR: Failed to obtain credentials")
        return 1
    
    print("Successfully obtained GCP credentials")
    
    # Test GCP services
    try:
        # Import only when needed
        from google.cloud import storage, bigquery
        
        # Test Storage
        project_id = config['gcp']['project_id']
        bucket_name = config['gcp']['storage']['bucket_name']
        print(f"Testing connection to Cloud Storage bucket: {bucket_name}")
        
        storage_client = storage.Client(project=project_id, credentials=credentials)
        try:
            bucket = storage_client.get_bucket(bucket_name)
            print(f"Successfully connected to bucket: {bucket.name}")
        except Exception as e:
            print(f"ERROR: Could not access bucket '{bucket_name}': {e}")
            print("You may need to create this bucket in the GCP Console")
            
        # Test BigQuery
        dataset_id = config['gcp']['bigquery']['dataset_id']
        print(f"Testing connection to BigQuery dataset: {dataset_id}")
        
        bigquery_client = bigquery.Client(project=project_id, credentials=credentials)
        try:
            dataset_ref = f"{project_id}.{dataset_id}"
            dataset = bigquery_client.get_dataset(dataset_ref)
            print(f"Successfully connected to dataset: {dataset.dataset_id}")
        except Exception as e:
            print(f"ERROR: Could not access dataset '{dataset_id}': {e}")
            print("You may need to create this dataset in the GCP Console")
        
        # Test table access
        vehicles_table = config['gcp']['bigquery']['vehicles_table']
        print(f"Testing access to BigQuery table: {vehicles_table}")
        
        try:
            table_ref = f"{project_id}.{dataset_id}.{vehicles_table}"
            table = bigquery_client.get_table(table_ref)
            print(f"Successfully connected to table: {table.table_id}")
        except Exception as e:
            print(f"ERROR: Could not access table '{vehicles_table}': {e}")
            print("You may need to create this table in BigQuery. Schema should match your database.")
        
        print("\nCloud connectivity test completed")
        return 0
    
    except Exception as e:
        print(f"ERROR: Failed to test GCP services: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())