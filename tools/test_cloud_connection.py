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
    
    print(f"Testing cloud co