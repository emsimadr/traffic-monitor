from __future__ import annotations

import os
from typing import Any, Dict

import yaml


class ConfigService:
    """
    Manages layered config:
    - config/default.yaml (checked in, universal defaults)
    - config/config.yaml (deployment-specific overrides)
    - data/calibration/site.yaml (site-specific calibration)
    
    The merge order is: default → config → calibration
    Calibration overrides config for calibration-specific keys.
    """

    DEFAULT_PATH = os.path.join("config", "default.yaml")
    OVERRIDES_PATH = os.path.join("config", "config.yaml")

    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        for k, v in (override or {}).items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                ConfigService._deep_merge(base[k], v)
            else:
                base[k] = v
        return base

    @staticmethod
    def load_default() -> Dict[str, Any]:
        if not os.path.exists(ConfigService.DEFAULT_PATH):
            return {}
        with open(ConfigService.DEFAULT_PATH, "r") as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def load_overrides() -> Dict[str, Any]:
        if not os.path.exists(ConfigService.OVERRIDES_PATH):
            return {}
        with open(ConfigService.OVERRIDES_PATH, "r") as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def load_effective_config() -> Dict[str, Any]:
        """
        Load effective configuration with all layers merged.
        
        Merge order:
        1. default.yaml (base defaults)
        2. config.yaml (deployment overrides)
        3. site.yaml (calibration overrides)
        
        Returns:
            Merged configuration dict.
        """
        merged = ConfigService.load_default()
        overrides = ConfigService.load_overrides()
        merged = ConfigService._deep_merge(merged, overrides)
        
        # Merge calibration layer (if exists)
        try:
            from .calibration_service import CalibrationService
            calibration = CalibrationService.load()
            if calibration:
                merged = CalibrationService.merge_into_config(merged, calibration)
        except Exception as e:
            # Calibration is optional, don't fail if it's missing
            import logging
            logging.debug(f"No calibration loaded: {e}")
        
        return merged

    @staticmethod
    def save_overrides(overrides: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(ConfigService.OVERRIDES_PATH) or ".", exist_ok=True)
        with open(ConfigService.OVERRIDES_PATH, "w") as f:
            yaml.safe_dump(overrides or {}, f, sort_keys=False)


