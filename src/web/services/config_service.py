from __future__ import annotations

import os
from typing import Any, Dict

import yaml


class ConfigService:
    """
    Manages layered config:
    - config/default.yaml (checked in)
    - config/config.yaml (local overrides)
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
        merged = ConfigService.load_default()
        overrides = ConfigService.load_overrides()
        return ConfigService._deep_merge(merged, overrides)

    @staticmethod
    def save_overrides(overrides: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(ConfigService.OVERRIDES_PATH) or ".", exist_ok=True)
        with open(ConfigService.OVERRIDES_PATH, "w") as f:
            yaml.safe_dump(overrides or {}, f, sort_keys=False)


