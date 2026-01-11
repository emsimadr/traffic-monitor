"""
Calibration service for managing site-specific geometry and measurements.

Calibration data includes:
- Gate line coordinates (measured once, rarely changed)
- Direction labels (site-specific)
- Camera transforms (rotate, flip)
- Future: Speed calibration (pixels_per_meter)

This is separate from configuration (operational settings).
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional
from datetime import datetime

import yaml


class CalibrationService:
    """
    Manages site-specific calibration data.
    
    Calibration is stored in data/calibration/site.yaml and includes:
    - Gate line geometry
    - Direction labels
    - Camera orientation
    - Speed calibration (future)
    
    This is separate from config.yaml which contains operational settings.
    """
    
    CALIBRATION_PATH = os.path.join("data", "calibration", "site.yaml")
    
    @staticmethod
    def load() -> Optional[Dict[str, Any]]:
        """
        Load site calibration data.
        
        Returns:
            Calibration dict, or None if file doesn't exist.
        """
        if not os.path.exists(CalibrationService.CALIBRATION_PATH):
            logging.debug(f"No calibration file at {CalibrationService.CALIBRATION_PATH}")
            return None
        
        try:
            with open(CalibrationService.CALIBRATION_PATH, "r") as f:
                calibration = yaml.safe_load(f) or {}
                logging.info(f"Loaded calibration from {CalibrationService.CALIBRATION_PATH}")
                return calibration
        except Exception as e:
            logging.error(f"Failed to load calibration: {e}")
            return None
    
    @staticmethod
    def save(calibration: Dict[str, Any], add_metadata: bool = True) -> None:
        """
        Save site calibration data.
        
        Args:
            calibration: Calibration dict to save.
            add_metadata: Whether to add/update metadata fields.
        """
        # Ensure directory exists
        calib_dir = os.path.dirname(CalibrationService.CALIBRATION_PATH)
        if calib_dir:
            os.makedirs(calib_dir, exist_ok=True)
        
        # Add metadata if requested
        if add_metadata:
            if "_metadata" not in calibration:
                calibration["_metadata"] = {}
            
            calibration["_metadata"]["last_updated"] = datetime.now().isoformat()
            
            # Add creation timestamp if new file
            if not os.path.exists(CalibrationService.CALIBRATION_PATH):
                calibration["_metadata"]["created"] = datetime.now().isoformat()
        
        try:
            with open(CalibrationService.CALIBRATION_PATH, "w") as f:
                # Add header comment
                f.write("# Site-specific calibration data\n")
                f.write("# This file contains measured geometry and orientation specific to this deployment.\n")
                f.write("# Do not check into source control (site-specific).\n\n")
                yaml.safe_dump(calibration, f, sort_keys=False, default_flow_style=False)
            
            logging.info(f"Saved calibration to {CalibrationService.CALIBRATION_PATH}")
        except Exception as e:
            logging.error(f"Failed to save calibration: {e}")
            raise
    
    @staticmethod
    def exists() -> bool:
        """Check if calibration file exists."""
        return os.path.exists(CalibrationService.CALIBRATION_PATH)
    
    @staticmethod
    def extract_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract calibration data from a config dict.
        
        This is used during migration from config.yaml to site.yaml.
        
        Args:
            config: Full config dict.
            
        Returns:
            Dict containing only calibration data.
        """
        calibration: Dict[str, Any] = {}
        
        # Extract gate line geometry from counting config
        counting = config.get("counting", {}) or {}
        if counting:
            calib_counting = {}
            
            # Line coordinates (calibration data)
            if "line_a" in counting:
                calib_counting["line_a"] = counting["line_a"]
            if "line_b" in counting:
                calib_counting["line_b"] = counting["line_b"]
            
            # Direction labels (site-specific)
            if "direction_labels" in counting:
                calib_counting["direction_labels"] = counting["direction_labels"]
            
            if calib_counting:
                calibration["counting"] = calib_counting
        
        # Extract camera transforms (calibration data)
        camera = config.get("camera", {}) or {}
        if camera:
            calib_camera = {}
            
            # Orientation transforms (calibration data)
            if camera.get("rotate") not in (None, 0):
                calib_camera["rotate"] = camera["rotate"]
            if camera.get("flip_horizontal"):
                calib_camera["flip_horizontal"] = camera["flip_horizontal"]
            if camera.get("flip_vertical"):
                calib_camera["flip_vertical"] = camera["flip_vertical"]
            if camera.get("swap_rb"):
                calib_camera["swap_rb"] = camera["swap_rb"]
            
            if calib_camera:
                calibration["camera"] = calib_camera
        
        return calibration
    
    @staticmethod
    def merge_into_config(config: Dict[str, Any], calibration: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge calibration data into config dict.
        
        Calibration values override config values for the same keys.
        This allows site.yaml to override config.yaml for calibration fields.
        
        Args:
            config: Base config dict.
            calibration: Calibration dict (or None).
            
        Returns:
            Merged config dict.
        """
        if not calibration:
            return config
        
        # Deep copy to avoid modifying original
        import copy
        merged = copy.deepcopy(config)
        
        # Merge calibration sections
        for section in ["counting", "camera"]:
            if section in calibration:
                if section not in merged:
                    merged[section] = {}
                
                # Merge calibration values into config section
                for key, value in calibration[section].items():
                    merged[section][key] = value
        
        return merged

