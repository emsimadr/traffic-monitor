"""
RTSP credential injection utilities.

Provides a shared function for injecting RTSP credentials from a secrets file
into camera configuration. Used by both main.py and camera_service.py.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict
from urllib.parse import urlparse, urlunparse

import yaml


def inject_rtsp_credentials(camera_cfg: Dict[str, Any]) -> None:
    """
    Inject RTSP credentials from secrets file into camera config.
    
    This function handles the common pattern of loading RTSP credentials from
    a separate secrets file and injecting them into the device_id URL.
    
    Args:
        camera_cfg: Camera configuration dict (modified in-place).
            Expected keys:
            - secrets_file: Path to YAML file with username/password/rtsp_url
            - device_id: Current device_id (int for USB, string for RTSP/file)
    
    The secrets file should contain:
        username: <rtsp_username>
        password: <rtsp_password>
        rtsp_url: rtsp://host:port/path  # Optional, used if device_id is not RTSP
    
    If rtsp_url is provided in secrets and device_id is not already an RTSP URL,
    the rtsp_url from secrets will be used as the base URL.
    
    Credentials are injected as: rtsp://username:password@host:port/path
    """
    secrets_file = camera_cfg.get("secrets_file")
    if not secrets_file:
        return
    
    if not os.path.exists(secrets_file):
        logging.warning(f"Secrets file not found: {secrets_file}")
        return
    
    try:
        with open(secrets_file, "r") as f:
            secrets = yaml.safe_load(f) or {}
        
        username = secrets.get("username")
        password = secrets.get("password")
        rtsp_url_from_secrets = secrets.get("rtsp_url")
        device_id = camera_cfg.get("device_id", "")
        
        # Determine the base RTSP URL
        # Priority: existing RTSP device_id > rtsp_url from secrets
        if isinstance(device_id, str) and device_id.startswith("rtsp://"):
            base_url = device_id
        elif rtsp_url_from_secrets:
            base_url = rtsp_url_from_secrets
            logging.info("Using RTSP URL from secrets file")
        else:
            # No RTSP URL available, nothing to inject
            return
        
        # Inject credentials if available
        if username and password:
            if "@" not in base_url:
                # Parse and reconstruct URL with credentials
                parsed = urlparse(base_url)
                netloc = f"{username}:{password}@{parsed.hostname}"
                if parsed.port:
                    netloc += f":{parsed.port}"
                new_url = urlunparse((
                    parsed.scheme, netloc, parsed.path,
                    parsed.params, parsed.query, parsed.fragment
                ))
                camera_cfg["device_id"] = new_url
                logging.info("RTSP credentials injected into device URL")
            else:
                # URL already has credentials, just use it
                camera_cfg["device_id"] = base_url
        else:
            # No credentials, just use the base URL as-is
            if base_url != device_id:
                camera_cfg["device_id"] = base_url
                
    except Exception as e:
        logging.error(f"Failed to inject RTSP credentials: {e}")

