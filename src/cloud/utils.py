"""
Utility functions for cloud operations.
"""

import logging
import json
import os

def check_cloud_config(config):
    """
    Check if the cloud configuration is valid.
    
    Args:
        config: Cloud configuration dictionary
    
    Returns:
        Boolean indicating if the configuration is valid
    """
    try:
        # Check if config has the required structure
        if not isinstance(config, dict) or 'gcp' not in config:
            logging.error("Invalid cloud configuration: missing 'gcp' section")
            return False
        
        # Check required settings
        required_settings = [
            'project_id',
            'credentials_file',
            'storage.bucket_name',
            'bigquery.dataset_id',
            'sync.interval_minutes'
        ]
        
        for setting in required_settings:
            # Handle nested settings
            if '.' in setting:
                parts = setting.split('.')
                value = config['gcp']
                for part in parts:
                    if part not in value:
                        logging.error(f"Invalid cloud configuration: missing '{setting}'")
                        return False
                    value = value[part]
            else:
                if setting not in config['gcp']:
                    logging.error(f"Invalid cloud configuration: missing 'gcp.{setting}'")
                    return False
        
        return True
    
    except Exception as e:
        logging.error(f"Error validating cloud configuration: {e}")
        return False

def format_cloud_path(bucket_name, folder, filename):
    """
    Format a cloud storage path.
    
    Args:
        bucket_name: Name of the storage bucket
        folder: Folder path
        filename: Filename
    
    Returns:
        Formatted cloud path
    """
    return f"gs://{bucket_name}/{folder}/{filename}"