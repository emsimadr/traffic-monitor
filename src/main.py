"""
Main application for Milestone 1: Core Vehicle Detection & Data Collection.

This script initializes the camera, detects vehicles, and stores counts in a database.
It provides the foundation for the traffic monitoring system.

Usage:
    python src/main.py --config config/config.yaml --display

Arguments:
    --config: Path to configuration file
    --display: Enable visual display for debugging
    --record: Record video output
"""

import os
import sys
import argparse
import logging
import time
import yaml
import cv2
import numpy as np
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

# Import local modules
from camera.camera import create_camera, inject_rtsp_credentials
from analytics.counter import GateCounter, GateCounterConfig
from tracking.tracker import VehicleTracker
from detection.vehicle import VehicleDetector
from detection.bgsub_detector import BgSubDetector
from inference.cpu_backend import UltralyticsCpuBackend, CpuYoloConfig
from storage.db import Database
from cloud.sync import CloudSync
from cloud.utils import check_cloud_config
from ops.logging import setup_logging
from web.app import create_app
from web.state import state as web_state
import threading
import uvicorn

from runtime.context import RuntimeContext
from runtime.services import CountingService, FrameIngestService
from pipeline.engine import PipelineEngine, PipelineConfig, create_engine_from_config

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

        # Finally apply explicit config_path if it's not the local override file itself
        if os.path.exists(config_path) and os.path.abspath(config_path) != os.path.abspath(local_overrides_path):
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
        return False, "camera.device_id integer must be non-negative"
    
    if 'resolution' not in camera:
        return False, "Missing camera.resolution"
    if not isinstance(camera['resolution'], list) or len(camera['resolution']) != 2:
        return False, "camera.resolution must be a list of [width, height]"
    if not all(isinstance(x, int) and x > 0 for x in camera['resolution']):
        return False, "camera.resolution values must be positive integers"
    
    if 'fps' not in camera:
        return False, "Missing camera.fps"
    if not isinstance(camera['fps'], int) or camera['fps'] <= 0:
        return False, "camera.fps must be a positive integer"

    # Optional camera backend selector
    backend = camera.get('backend', 'opencv')
    if backend not in ('opencv', 'picamera2'):
        return False, "camera.backend must be one of: opencv, picamera2"
    if backend == 'picamera2':
        # Picamera2 doesn't use device_id; keep backward compat but ignore it.
        pass
    
    # Validate detection settings
    detection = config.get('detection', {})
    if 'min_contour_area' not in detection:
        # For YOLO mode this may not be required, but keep backward compatibility.
        detection.setdefault('min_contour_area', 1000)
    if not isinstance(detection.get('min_contour_area'), int) or detection.get('min_contour_area') <= 0:
        return False, "detection.min_contour_area must be a positive integer"

    # Detection backend selection (optional; defaults to bgsub)
    backend = detection.get('backend', 'bgsub')
    if backend not in ('bgsub', 'yolo'):
        return False, "detection.backend must be one of: bgsub, yolo"
    if backend == 'yolo':
        yolo_cfg = detection.get('yolo', {})
        if 'model' not in yolo_cfg or not isinstance(yolo_cfg.get('model'), str) or not yolo_cfg.get('model'):
            return False, "detection.yolo.model is required when detection.backend is 'yolo'"
        if 'conf_threshold' in yolo_cfg and not isinstance(yolo_cfg['conf_threshold'], (int, float)):
            return False, "detection.yolo.conf_threshold must be a number"
        if 'iou_threshold' in yolo_cfg and not isinstance(yolo_cfg['iou_threshold'], (int, float)):
            return False, "detection.yolo.iou_threshold must be a number"
    
    # Optional tracking settings (used by VehicleTracker)
    tracking = config.get('tracking', {}) or {}
    if tracking:
        if 'max_frames_since_seen' in tracking:
            mfs = tracking['max_frames_since_seen']
            if not isinstance(mfs, int) or mfs <= 0:
                return False, "tracking.max_frames_since_seen must be a positive integer"
        if 'min_trajectory_length' in tracking:
            mtl = tracking['min_trajectory_length']
            if not isinstance(mtl, int) or mtl <= 0:
                return False, "tracking.min_trajectory_length must be a positive integer"
        if 'iou_threshold' in tracking:
            iou = tracking['iou_threshold']
            if not isinstance(iou, (int, float)) or not (0 < iou <= 1):
                return False, "tracking.iou_threshold must be between 0 and 1"
    
    # Validate storage settings
    storage = config.get('storage', {})
    if 'local_database_path' not in storage:
        return False, "Missing storage.local_database_path"
    if not isinstance(storage['local_database_path'], str):
        return False, "storage.local_database_path must be a string"
    
    if 'retention_days' in storage:
        if not isinstance(storage['retention_days'], int) or storage['retention_days'] <= 0:
            return False, "storage.retention_days must be a positive integer"
    
    # Validate log settings
    if 'log_level' not in config:
        return False, "Missing log_level"
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if config['log_level'] not in valid_log_levels:
        return False, f"log_level must be one of: {', '.join(valid_log_levels)}"
    
    return True, None

def main():
    """Main application function."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Traffic Monitoring System - Milestone 1')
    parser.add_argument('--config', type=str, default='config/config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--display', action='store_true',
                        help='Enable visual display')
    parser.add_argument('--record', action='store_true',
                        help='Record video output')
    parser.add_argument('--new-engine', action='store_true',
                        help='Use new pipeline engine (experimental)')
    parser.add_argument('--legacy', action='store_true',
                        help='Force legacy main loop (overrides config)')
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Handle RTSP camera credentials if secrets_file is provided
    try:
        inject_rtsp_credentials(config["camera"])
    except Exception as e:
        logging.error(f"Error loading camera secrets: {e}")

    # Validate configuration
    is_valid, error_msg = validate_config(config)
    if not is_valid:
        logging.error(f"Configuration validation failed: {error_msg}")
        sys.exit(1)
    
    # Setup logging
    setup_logging(config['log_path'], config['log_level'])
    
    # Ensure data directory exists
    data_dir = os.path.dirname(config['storage']['local_database_path'])
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    # Create output directory if recording
    if args.record:
        output_dir = 'output/video'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    logging.info("Starting Traffic Monitoring System - Milestone 1")
    
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
            cloud_enabled=config['storage']['use_cloud_storage']
        )
        db.initialize()
        
        # Initialize cloud sync if configuration is available
        if cloud_config and config['storage']['use_cloud_storage']:
            try:
                cloud_sync = CloudSync(cloud_config, config['storage']['local_database_path'])
                if cloud_sync.is_cloud_enabled:
                    cloud_sync.start_sync_thread()
                    logging.info("Cloud synchronization started")
                else:
                    logging.warning("Cloud sync is disabled")
            except Exception as e:
                logging.error(f"Failed to initialize cloud sync: {e}")
                cloud_sync = None
        
        # Initialize camera
        camera = create_camera(config['camera'])

        # Initialize Web Interface
        web_state.set_database(db)
        web_state.set_config(config, args.config)
        web_state.update_system_stats({"start_time": time.time()})
        
        def run_web_app():
            uvicorn.run(
                create_app(),
                host="0.0.0.0",
                port=5000,
                log_level="info",
            )
            
        web_thread = threading.Thread(target=run_web_app, daemon=True)
        web_thread.start()
        logging.info("Web interface started on port 5000")
        
        # Initialize vehicle detector
        detector_backend = config['detection'].get('backend', 'bgsub')
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
        else:
            vehicle_detector = VehicleDetector(
                min_contour_area=config['detection']['min_contour_area'],
                detect_shadows=config['detection']['detect_shadows']
            )
            detector = BgSubDetector(vehicle_detector)
        
        # Initialize vehicle tracker
        tracking_cfg = config.get('tracking', {}) or {}
        tracker = VehicleTracker(
            max_frames_since_seen=int(tracking_cfg.get('max_frames_since_seen', 10)),
            min_trajectory_length=int(tracking_cfg.get('min_trajectory_length', 3)),
            iou_threshold=float(tracking_cfg.get('iou_threshold', 0.3)),
        )

        # Counting strategy configuration (gate-only)
        counting_cfg = config.get('counting', {}) or {}
        
        # Initialize counters
        vehicle_count = 0
        count_northbound = 0
        count_southbound = 0
        frame_count = 0
        last_count_time = time.time()
        last_cleanup_time = time.time()
        cleanup_interval = 86400  # 24 hours in seconds
        
        # Initialize video writer if recording
        video_writer = None
        if args.record:
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"{output_dir}/traffic_{timestamp}.avi"
            video_writer = cv2.VideoWriter(
                output_path,
                fourcc,
                config['camera']['fps'],
                tuple(config['camera']['resolution']),
                True
            )
        
        # Build runtime context and services
        ctx = RuntimeContext(
            config=config,
            db=db,
            cloud_sync=cloud_sync,
            camera=camera,
            detector=detector,
            tracker=tracker,
            counter=None,
            web_state=web_state,
        )
        counting_service = CountingService(ctx, counting_cfg)
        ingest = FrameIngestService(ctx, counting_service, counting_config_fallback=None)
        
        # Determine which engine to use
        # Priority: --legacy flag > --new-engine flag > config setting > default (legacy)
        use_new_engine = False
        if args.legacy:
            use_new_engine = False
            logging.info("Using legacy main loop (--legacy flag)")
        elif args.new_engine:
            use_new_engine = True
            logging.info("Using new pipeline engine (--new-engine flag)")
        else:
            pipeline_cfg = config.get("pipeline", {})
            use_new_engine = pipeline_cfg.get("use_new_engine", False)
            if use_new_engine:
                logging.info("Using new pipeline engine (config: pipeline.use_new_engine=true)")
            else:
                logging.info("Using legacy main loop (default)")
        
        # Run with new pipeline engine if enabled
        if use_new_engine:
            engine = create_engine_from_config(
                config=config,
                ctx=ctx,
                counting_service=counting_service,
                display=args.display,
                record=args.record,
            )
            engine.run()
            # Engine handles its own cleanup, skip legacy cleanup
            return
        
        # Legacy main processing loop
        consecutive_frame_failures = 0
        max_frame_failures = 10
        
        while True:
            # Read frame from camera
            ret, frame = camera.read()
            if not ret:
                consecutive_frame_failures += 1
                if consecutive_frame_failures >= max_frame_failures:
                    logging.error(f"Too many consecutive frame read failures ({consecutive_frame_failures}), exiting")
                    break
                logging.warning(f"Failed to read frame ({consecutive_frame_failures}/{max_frame_failures}), continuing...")
                time.sleep(1)  # Wait before retrying
                continue
            
            # Reset failure counter on success
            consecutive_frame_failures = 0
            
            # Process frame through ingest service (detect -> track -> count)
            events = ingest.handle_frame(frame)
            
            # Accumulate counts for UI (line-mode compatibility)
            for event in events:
                vehicle_id = event.track_id
                direction = event.direction
                vehicle_count += 1
                if direction in ("northbound", "A_TO_B"):
                    count_northbound += 1
                elif direction in ("southbound", "B_TO_A"):
                    count_southbound += 1
                    
                logging.info(f"Vehicle {vehicle_id} detected! Direction: {direction}, Count: {vehicle_count}")
            
            # Draw tracked vehicles with IDs
            if args.display or args.record:
                for tracked_vehicle in tracker.get_active_tracks():
                    x1, y1, x2, y2 = map(int, tracked_vehicle.bbox)
                    color = (255, 0, 0) if tracked_vehicle.has_been_counted else (0, 255, 0)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    # Draw vehicle ID
                    cv2.putText(
                        frame,
                        f"ID: {tracked_vehicle.vehicle_id}",
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        2
                    )
            
            # Display vehicle count
            if args.display or args.record:
                cv2.putText(
                    frame,
                    f"Total Count: {vehicle_count}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    2
                )
                cv2.putText(
                    frame,
                    f"Northbound: {count_northbound}",
                    (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 0, 0),
                    2
                )
                cv2.putText(
                    frame,
                    f"Southbound: {count_southbound}",
                    (10, 100),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2
                )
            
            # Display frame
            if args.display:
                cv2.imshow('Traffic Monitor', frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
            
            # Write frame to video if recording
            if args.record and video_writer is not None:
                video_writer.write(frame)
            
            # Increment frame counter
            frame_count += 1
            
            # Log count every minute
            current_time = time.time()
            if current_time - last_count_time >= 60:
                logging.info(f"Current vehicle count: {vehicle_count}")
                last_count_time = current_time
                
                # Update aggregated statistics
                db.update_hourly_counts()
                db.update_daily_counts()
            
            # Run data cleanup periodically
            if current_time - last_cleanup_time >= cleanup_interval:
                retention_days = config['storage'].get('retention_days', 30)
                db.cleanup_old_data(retention_days=retention_days)
                last_cleanup_time = current_time
                logging.info(f"Data cleanup completed (retention: {retention_days} days)")
                
                # Upload video sample if recording and cloud is enabled
                if args.record and cloud_sync and cloud_sync.is_cloud_enabled and video_writer:
                    if frame_count > config['camera']['fps'] * 60:  # At least 1 minute of footage
                        video_writer.release()
                        logging.info(f"Saved video sample: {output_path}")
                        
                        # Upload to cloud
                        metadata = {
                            "timestamp": str(datetime.now()),
                            "vehicle_count": str(vehicle_count),
                            "description": "Traffic sample"
                        }
                        cloud_path = cloud_sync.upload_video_sample(output_path, metadata)
                        if cloud_path:
                            logging.info(f"Uploaded video to: {cloud_path}")
                        
                        # Create new video writer
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_path = f"{output_dir}/traffic_{timestamp}.avi"
                        video_writer = cv2.VideoWriter(
                            output_path,
                            fourcc,
                            config['camera']['fps'],
                            tuple(config['camera']['resolution']),
                            True
                        )
                        frame_count = 0
    
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    except Exception as e:
        logging.error(f"Error in main loop: {e}")
        import traceback
        traceback.print_exc()
        # Try to continue if it's a recoverable error
        if isinstance(e, (IOError, OSError, RuntimeError)):
            logging.warning("Recoverable error detected, attempting to continue...")
            time.sleep(5)  # Wait before retrying
    finally:
        # Clean up resources
        if 'camera' in locals():
            camera.release()
        if 'db' in locals():
            db.close()
        if cloud_sync:
            cloud_sync.stop_sync_thread()
        if args.display:
            cv2.destroyAllWindows()
        if args.record and 'video_writer' in locals() and video_writer is not None:
            video_writer.release()
        
        logging.info("Traffic Monitoring System stopped")

if __name__ == "__main__":
    main()