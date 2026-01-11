#!/usr/bin/env python
"""
Migration tool: Extract calibration data from config.yaml to site.yaml

This tool helps migrate from the old single-file configuration to the new
3-layer architecture (default → config → calibration).

Usage:
    python tools/migrate_config_to_calibration.py [--dry-run]

What it does:
1. Reads config/config.yaml
2. Extracts calibration data (gate lines, camera transforms, direction labels)
3. Creates data/calibration/site.yaml with extracted calibration
4. Optionally removes calibration data from config.yaml (with backup)

This is a one-time migration. After running, you'll have:
- config/config.yaml: operational settings only
- data/calibration/site.yaml: site-specific geometry

The tool is safe and creates backups before modifying files.
"""

import os
import sys
import yaml
import shutil
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path to import services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.web.services.config_service import ConfigService
from src.web.services.calibration_service import CalibrationService


def backup_file(filepath: str) -> str:
    """Create a timestamped backup of a file."""
    if not os.path.exists(filepath):
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.backup.{timestamp}"
    shutil.copy2(filepath, backup_path)
    print(f"✓ Created backup: {backup_path}")
    return backup_path


def migrate(dry_run: bool = False):
    """
    Migrate calibration data from config.yaml to site.yaml.
    
    Args:
        dry_run: If True, only show what would be done without making changes.
    """
    print("=" * 70)
    print("Config → Calibration Migration Tool")
    print("=" * 70)
    print()
    
    # Check if config.yaml exists
    if not os.path.exists(ConfigService.OVERRIDES_PATH):
        print(f"✗ No config file found at {ConfigService.OVERRIDES_PATH}")
        print("  Nothing to migrate.")
        return 0
    
    # Check if site.yaml already exists
    if CalibrationService.exists():
        print(f"✓ Calibration file already exists at {CalibrationService.CALIBRATION_PATH}")
        response = input("  Overwrite existing calibration? [y/N]: ")
        if response.lower() != 'y':
            print("  Migration cancelled.")
            return 1
    
    # Load config.yaml
    print(f"\n1. Reading {ConfigService.OVERRIDES_PATH}...")
    config = ConfigService.load_overrides()
    if not config:
        print("  ✗ Config file is empty. Nothing to migrate.")
        return 1
    
    # Extract calibration data
    print("\n2. Extracting calibration data...")
    calibration = CalibrationService.extract_from_config(config)
    
    if not calibration:
        print("  ✗ No calibration data found in config.yaml")
        print("  (Looking for: gate lines, camera transforms, direction labels)")
        return 1
    
    print("  ✓ Found calibration data:")
    if "counting" in calibration:
        if "line_a" in calibration["counting"]:
            print("    - Gate line A")
        if "line_b" in calibration["counting"]:
            print("    - Gate line B")
        if "direction_labels" in calibration["counting"]:
            print("    - Direction labels")
    if "camera" in calibration:
        print("    - Camera transforms")
    
    # Preview calibration
    print("\n3. Calibration to be saved:")
    print("-" * 70)
    print(yaml.safe_dump(calibration, sort_keys=False, default_flow_style=False))
    print("-" * 70)
    
    if dry_run:
        print("\n[DRY RUN] Would save calibration to:")
        print(f"  {CalibrationService.CALIBRATION_PATH}")
        print("\n[DRY RUN] Would remove calibration data from:")
        print(f"  {ConfigService.OVERRIDES_PATH}")
        return 0
    
    # Confirm
    print()
    response = input("Proceed with migration? [y/N]: ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return 1
    
    # Create backup of config.yaml
    print("\n4. Creating backup...")
    backup_path = backup_file(ConfigService.OVERRIDES_PATH)
    
    # Save calibration to site.yaml
    print(f"\n5. Saving calibration to {CalibrationService.CALIBRATION_PATH}...")
    try:
        CalibrationService.save(calibration, add_metadata=True)
        print("  ✓ Calibration saved successfully")
    except Exception as e:
        print(f"  ✗ Failed to save calibration: {e}")
        return 1
    
    # Remove calibration data from config.yaml
    print(f"\n6. Cleaning up {ConfigService.OVERRIDES_PATH}...")
    cleaned_config = remove_calibration_from_config(config)
    
    if cleaned_config != config:
        try:
            with open(ConfigService.OVERRIDES_PATH, "w") as f:
                yaml.safe_dump(cleaned_config, f, sort_keys=False, default_flow_style=False)
            print("  ✓ Removed calibration data from config.yaml")
        except Exception as e:
            print(f"  ✗ Failed to update config.yaml: {e}")
            print(f"  Restore from backup: {backup_path}")
            return 1
    else:
        print("  ℹ No changes needed to config.yaml")
    
    print("\n" + "=" * 70)
    print("✓ Migration complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print(f"  1. Review {CalibrationService.CALIBRATION_PATH}")
    print(f"  2. Review {ConfigService.OVERRIDES_PATH}")
    print(f"  3. Restart the application to use new calibration")
    print(f"  4. Add data/calibration/site.yaml to .gitignore (site-specific)")
    print()
    print(f"Backup saved at: {backup_path}")
    print()
    
    return 0


def remove_calibration_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove calibration data from config dict.
    
    Returns a new dict with calibration data removed.
    """
    import copy
    cleaned = copy.deepcopy(config)
    
    # Remove calibration fields from counting
    if "counting" in cleaned:
        # Keep operational settings, remove calibration data
        counting = cleaned["counting"]
        for key in ["line_a", "line_b", "direction_labels"]:
            counting.pop(key, None)
        
        # If counting section is now empty or only has operational settings, keep it
        if not counting:
            cleaned.pop("counting")
    
    # Remove calibration fields from camera
    if "camera" in cleaned:
        camera = cleaned["camera"]
        for key in ["rotate", "flip_horizontal", "flip_vertical", "swap_rb"]:
            # Only remove if it's a non-default value (calibration)
            if key in camera and camera[key] in (0, False):
                camera.pop(key)
            elif key in camera:
                camera.pop(key)
        
        # Remove camera section if empty or only has operational settings
        operational_keys = ["backend", "device_id", "secrets_file", "resolution", "fps"]
        if not any(k in camera for k in operational_keys):
            if not camera:
                cleaned.pop("camera")
    
    return cleaned


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate calibration from config.yaml to site.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    args = parser.parse_args()
    
    sys.exit(migrate(dry_run=args.dry_run))

