"""
Authentication module for GCP services.
"""

import os
import logging
from google.oauth2 import service_account

def get_credentials(credentials_path):
    """
    Get GCP credentials for authentication.
    
    Args:
        credentials_path: Path to service account JSON file
    
    Returns:
        Credentials object or None if failed
    """
    try:
        # Check if credentials file exists
        if not os.path.exists(credentials_path):
            logging.warning(f"GCP credentials file not found: {credentials_path}")
            return None
        
        # Load credentials
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        
        logging.info("GCP credentials loaded successfully")
        return credentials
    
    except Exception as e:
        logging.error(f"Failed to load GCP credentials: {e}")
        return None