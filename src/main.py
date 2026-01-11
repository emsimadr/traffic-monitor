"""
Traffic Monitoring System.

This script initializes the observation source, detection, tracking, and counting
pipeline, and stores events in a database. A web interface provides live video
streaming and statistics.

Usage:
    python src/main.py --config config/config.yaml --display
    python src/main.py --stop  # Stop running instance

Arguments:
    --config: Path to configuration file
    --display: Enable visual display for debugging
    --record: Record video output
    --stop: Stop any running instance and exit
    --kill-existing: Kill any existing instance before starting
"""

import os
import sys
import argparse
import logging
import time
import yaml
import threading
from typing import Dict, Any, Tuple, Optional

import cv2
import uvicorn

from detection.vehicle import VehicleDetector
from detection.bgsub_detector import BgSubDetector
from tracking.tracker import VehicleTracker
from inference.cpu_backend import UltralyticsCpuBackend, CpuYoloConfig
from storage.database import Database
from cloud.sync import CloudSync
from cloud.utils import check_cloud_config
from ops.logging import setup_logging
from ops.process import ensure_single_instance, stop_existing_instance
from web.app import create_app
from web.state import state as web_state

from runtime.context import RuntimeContext
from pipeline.engine import create_engine_from_config
from observation import create_source_from_config


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge override into base and return base."""
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration with layering:
    - `config/default.yaml` (checked in)
    - `config/config.yaml` (local overrides)
    - plus any explicitly provided `--config` path (treated as overrides)
    """
    try:
        base_path = os.path.join(os.path.dirname(config_path), "default.yaml")
        base_cfg: Dict[str, Any] = {}
        if os.path.exists(base_path):
            with open(base_path, "r") as f:
                base_cfg = yaml.safe_load(f) or {}

        local_overrides_path = os.path.join(os.path.dirname(config_path), "config.yaml")
        local_cfg: Dict[str, Any] = {}
        if os.path.exists(local_overrides_path):
            with open(local_overrides_path, "r") as f:
                local_cfg = yaml.safe_load(f) or {}

        merged = _deep_merge(base_cfg, local_cfg)

        # Apply explicit config_path if different from local override
        if (os.path.exists(config_path) and 
            os.path.abspath(config_path) != os.path.abspath(local_overrides_path)):
            with open(config_path, "r") as f:
                explicit_cfg = yaml.safe_load(f) or {}
            merged = _deep_merge(merged, explicit_cfg)

        return merged
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        sys.exit(1)


def validate_config(config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate configuration file structure and values.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Required top-level sections
    required_sections = ['camera', 'detection', 'storage', 'log_path', 'log_level']
    for section in required_sections:
        if section not in config:
            return False, f"Missing required configuration section: {section}"
    
    # Validate camera settings
    camera = config.get('camera', {})
    if 'device_id' not in camera:
        return False, "Missing camera.device_id"
    if not isinstance(camera['device_id'], (int, str)):
        return False, "camera.device_id must be an integer (index) or string (URL)"
    if isinstance(camera['device_id'], int) and camera['device_id'] < 0:
        return False, "camera.device_id must be non-negative when using an integer index"
    
    if 'resolution' not in camera:
        return False, "Missing camera.resolution"
    if not isinstance(camera['resolution'], list) or len(camera['resolution']) != 2:
        return False, "camera.resolution must be a list of [width, height]"
    
    if 'fps' not in camera:
        return False, "Missing camera.fps"
    if not isinstance(camera['fps'], int) or camera['fps'] <= 0:
        return False, "camera.fps must be a positive integer"

    # Camera backend validation
    backend = camera.get('backend', 'opencv')
    if backend not in ('opencv', 'picamera2'):
        return False, "camera.backend must be one of: opencv, picamera2"
    
    # Validate detection settings
    detection = config.get('detection', {})
    detection.setdefault('min_contour_area', 1000)
    
    backend = detection.get('backend', 'bgsub')
    if backend not in ('bgsub', 'yolo', 'hailo'):
        return False, "detection.backend must be one of: bgsub, yolo, hailo"
    if backend == 'yolo':
        yolo_cfg = detection.get('yolo', {})
        if not yolo_cfg.get('model'):
            return False, "detection.yolo.model is required when detection.backend is 'yolo'"
    if backend == 'hailo':
        hailo_cfg = detection.get('hailo', {})
        if not hailo_cfg.get('hef_path'):
            return False, "detection.hailo.hef_path is required when detection.backend is 'hailo'"
    
    # Validate storage settings
    storage = config.get('storage', {})
    if 'local_database_path' not in storage:
        return False, "Missing storage.local_database_path"
    
    # Validate log settings
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if config['log_level'] not in valid_log_levels:
        return False, f"log_level must be one of: {', '.join(valid_log_levels)}"
    
    # Validate tracking settings if present
    tracking = config.get('tracking', {})
    if tracking:
        iou_threshold = tracking.get('iou_threshold')
        if iou_threshold is not None:
            if not isinstance(iou_threshold, (int, float)) or iou_threshold < 0 or iou_threshold > 1:
                return False, "tracking.iou_threshold must be a number between 0 and 1"
    
    return True, None


def main():
    """Main application function."""
    parser = argparse.ArgumentParser(description='Traffic Monitoring System')
    parser.add_argument('--config', type=str, default='config/config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--display', action='store_true',
                        help='Enable visual display')
    parser.add_argument('--record', action='store_true',
                        help='Record video output')
    parser.add_argument('--stop', action='store_true',
                        help='Stop any running instance and exit')
    parser.add_argument('--kill-existing', action='store_true',
                        help='Kill any existing instance before starting')
    args = parser.parse_args()
    
    # Handle --stop command
    if args.stop:
        success = stop_existing_instance()
        sys.exit(0 if success else 1)
    
    # Ensure single instance
    if not ensure_single_instance(kill_existing=args.kill_existing):
        sys.exit(1)
    
    # Load and validate configuration
    config = load_config(args.config)
    
    is_valid, error_msg = validate_config(config)
    if not is_valid:
        logging.error(f"Configuration validation failed: {error_msg}")
        sys.exit(1)
    
    # Setup logging
    setup_logging(config['log_path'], config['log_level'])
    
    # Ensure data directory exists
    data_dir = os.path.dirname(config['storage']['local_database_path'])
    if data_dir and not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    logging.info("Starting Traffic Monitoring System")
    
    # Load cloud configuration if available
    cloud_sync = None
    cloud_config_path = os.path.join(os.path.dirname(args.config), 'cloud_config.yaml')
    cloud_config = None
    
    if os.path.exists(cloud_config_path):
        try:
            with open(cloud_config_path, 'r') as f:
                cloud_config = yaml.safe_load(f)
            if check_cloud_config(cloud_config):
                logging.info("Cloud configuration loaded")
            else:
                logging.warning("Invalid cloud configuration, running in local-only mode")
                cloud_config = None
        except Exception as e:
            logging.error(f"Error loading cloud configuration: {e}")
            cloud_config = None
    else:
        logging.info("Cloud configuration not found, running in local-only mode")
    
    try:
        # Initialize database
        db = Database(
            config['storage']['local_database_path'], 
            cloud_enabled=config['storage'].get('use_cloud_storage', False)
        )
        db.initialize()
        
        # Initialize cloud sync
        if cloud_config and config['storage'].get('use_cloud_storage'):
            try:
                cloud_sync = CloudSync(cloud_config, config['storage']['local_database_path'])
                if cloud_sync.is_cloud_enabled:
                    cloud_sync.start_sync_thread()
                    logging.info("Cloud synchronization started")
            except Exception as e:
                logging.error(f"Failed to initialize cloud sync: {e}")
                cloud_sync = None
        
        # Initialize detector
        detector_backend = config['detection'].get('backend', 'bgsub')
        logging.info(f"Detection backend: {detector_backend}")
        
        if detector_backend == 'yolo':
            ycfg = config['detection'].get('yolo', {})
            detector = UltralyticsCpuBackend(
                CpuYoloConfig(
                    model=ycfg['model'],
                    conf_threshold=float(ycfg.get('conf_threshold', 0.25)),
                    iou_threshold=float(ycfg.get('iou_threshold', 0.45)),
                    classes=ycfg.get('classes'),
                    class_name_overrides=ycfg.get('class_name_overrides'),
                )
            )
            # Log device info (GPU vs CPU)
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_name = torch.cuda.get_device_name(0)
                    logging.info(f"YOLO inference device: GPU ({gpu_name})")
                else:
                    logging.info("YOLO inference device: CPU (CUDA not available)")
            except ImportError:
                logging.info("YOLO inference device: CPU (PyTorch not installed)")
        elif detector_backend == 'hailo':
            # Phase 2: Hailo AI HAT+ backend (not yet implemented)
            # Will be implemented in src/inference/hailo_backend.py
            raise NotImplementedError(
                "Hailo backend is not yet implemented. "
                "Use detection.backend='yolo' for GPU dev, or 'bgsub' for CPU fallback. "
                "See PLAN.md Milestone 2 for Hailo integration status."
            )
        else:
            # Default: background subtraction (works everywhere, no dependencies)
            logging.info("Using background subtraction (no ML model)")
            vehicle_detector = VehicleDetector(
                min_contour_area=config['detection']['min_contour_area'],
                detect_shadows=config['detection'].get('detect_shadows', True)
            )
            detector = BgSubDetector(vehicle_detector)
        
        # Initialize tracker
        tracking_cfg = config.get('tracking', {}) or {}
        tracker = VehicleTracker(
            max_frames_since_seen=int(tracking_cfg.get('max_frames_since_seen', 10)),
            min_trajectory_length=int(tracking_cfg.get('min_trajectory_length', 3)),
            iou_threshold=float(tracking_cfg.get('iou_threshold', 0.3)),
        )

        # Initialize web state
        web_state.set_database(db)
        web_state.set_config(config, args.config)
        web_state.update_system_stats({"start_time": time.time()})
        
        # Start web server in background
        def run_web_app():
            # Use uvicorn.Config/Server to avoid installing signal handlers in the thread,
            # which can conflict with the main thread and OpenCV on Windows.
            config = uvicorn.Config(
                create_app(),
                host="0.0.0.0",
                port=5000,
                log_level="warning",
                loop="asyncio",
            )
            server = uvicorn.Server(config)
            # Disable signal handlers to allow running in a thread
            server.install_signal_handlers = lambda: None
            server.run()
            
        web_thread = threading.Thread(target=run_web_app, daemon=True)
        web_thread.start()
        logging.info("Web interface started on http://0.0.0.0:5000")
        
        # Build runtime context
        ctx = RuntimeContext(
            config=config,
            db=db,
            cloud_sync=cloud_sync,
            camera=None,  # Not used by pipeline engine
            detector=detector,
            tracker=tracker,
            counter=None,
            web_state=web_state,
        )
        
        # Create and run pipeline engine
        engine = create_engine_from_config(
            config=config,
            ctx=ctx,
            display=args.display,
            record=args.record,
        )
        
        logging.info("Starting pipeline engine...")
        engine.run()
        
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    except Exception as e:
        logging.error(f"Error in main: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db' in locals():
            db.close()
        if cloud_sync:
            cloud_sync.stop_sync_thread()
        if args.display:
            cv2.destroyAllWindows()
        logging.info("Traffic Monitoring System stopped")


if __name__ == "__main__":
    main()
