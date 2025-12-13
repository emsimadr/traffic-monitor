"""
GCP authentication module for loading service account credentials.

This module provides functions to authenticate with Google Cloud Platform
using service account credentials stored in a JSON file.
"""

import os
import logging
from typing import Optional
from google.oauth2 import service_account
from google.auth import credentials as auth_credentials


def get_credentials(credentials_path: str) -> Optional[auth_credentials.Credentials]:
    """
    Load GCP service account credentials from a JSON file.
    
    Args:
        credentials_path: Path to the service account JSON credentials file
        
    Returns:
        Service account credentials object, or None if loading failed
        
    Example:
        >>> creds = get_credentials("secrets/gcp-credentials.json")
        >>> if creds:
        ...     print("Credentials loaded successfully")
    """
    if not credentials_path:
        logging.error("Credentials path is empty")
        return None
    
    if not os.path.exists(credentials_path):
        logging.error(f"Credentials file not found: {credentials_path}")
        return None
    
    if not os.path.isfile(credentials_path):
        logging.error(f"Credentials path is not a file: {credentials_path}")
        return None
    
    try:
        credentials_obj = service_account.Credentials.from_service_account_file(
            credentials_path
        )
        logging.info(f"Successfully loaded credentials from {credentials_path}")
        return credentials_obj
        
    except Exception as e:
        logging.error(f"Failed to load credentials from {credentials_path}: {e}")
        return None
