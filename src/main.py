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
from camera.capture import VideoCapture
from detection.vehicle import VehicleDetector
from detection.tracker import VehicleTracker
from storage.database import Database
from cloud.sync import CloudSync
from cloud.utils import check_cloud_config

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        sys.exit(1)

def setup_logging(log_path: str, log_level: str) -> None:
    """Set up logging based on configuration."""
    log_dir = os.path.dirname(log_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler()
        ]
    )

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
    
    # Validate detection settings
    detection = config.get('detection', {})
    if 'min_contour_area' not in detection:
        return False, "Missing detection.min_contour_area"
    if not isinstance(detection['min_contour_area'], int) or detection['min_contour_area'] <= 0:
        return False, "detection.min_contour_area must be a positive integer"
    
    # Counting line can be a float (0-1, Y-position) or a list of two points [[x1,y1], [x2,y2]]
    if 'counting_line' in detection:
        line = detection['counting_line']
        if isinstance(line, (int, float)):
            if not 0 <= line <= 1:
                return False, "detection.counting_line must be between 0 and 1"
        elif isinstance(line, list):
            if len(line) != 2 or not all(isinstance(p, list) and len(p) == 2 for p in line):
                return False, "detection.counting_line must be [[x1,y1], [x2,y2]]"
        else:
            return False, "detection.counting_line must be a number or list of points"
    elif 'counting_line_position' not in detection:
        # Fallback for old config
        return False, "Missing detection.counting_line or detection.counting_line_position"
    
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
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Handle camera credentials if secrets_file is provided
    if isinstance(config['camera']['device_id'], str) and 'secrets_file' in config['camera']:
        try:
            secrets_path = config['camera']['secrets_file']
            if os.path.exists(secrets_path):
                with open(secrets_path, 'r') as f:
                    secrets = yaml.safe_load(f)
                
                device_url = config['camera']['device_id']
                if 'username' in secrets and 'password' in secrets:
                    # Inject credentials into RTSP URL
                    # Assumes format rtsp://ip/path -> rtsp://user:pass@ip/path
                    if device_url.startswith("rtsp://"):
                        protocol, rest = device_url.split("://", 1)
                        auth_url = f"{protocol}://{secrets['username']}:{secrets['password']}@{rest}"
                        config['camera']['device_id'] = auth_url
                        logging.info("Injected camera credentials from secrets file")
            else:
                logging.warning(f"Secrets file not found: {secrets_path}")
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
        camera = VideoCapture(
            device_id=config['camera']['device_id'],
            resolution=tuple(config['camera']['resolution']),
            fps=config['camera']['fps'],
            rtsp_transport=config['camera'].get('rtsp_transport', 'tcp')
        )
        
        # Initialize vehicle detector
        detector = VehicleDetector(
            min_contour_area=config['detection']['min_contour_area'],
            detect_shadows=config['detection']['detect_shadows']
        )
        
        # Initialize vehicle tracker
        tracker = VehicleTracker(
            max_frames_since_seen=10,
            min_trajectory_length=3,
            iou_threshold=0.3
        )
        
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
        
        # Define counting line
        # Can be a single float (Y-position ratio) or a list of points [[x1, y1], [x2, y2]] (ratios)
        if 'counting_line' in config['detection']:
            counting_config = config['detection']['counting_line']
        else:
            counting_config = config['detection']['counting_line_position']
        
        # Main processing loop
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
            
            # Process frame for vehicle detection
            vehicles = detector.detect(frame)
            
            # Calculate counting line in pixels
            frame_height, frame_width = frame.shape[:2]
            
            if isinstance(counting_config, (int, float)):
                # Horizontal line case
                line_y = int(frame_height * counting_config)
                counting_line = [(0, line_y), (frame_width, line_y)]
            else:
                # Diagonal line case
                p1 = (int(counting_config[0][0] * frame_width), int(counting_config[0][1] * frame_height))
                p2 = (int(counting_config[1][0] * frame_width), int(counting_config[1][1] * frame_height))
                counting_line = [p1, p2]
            
            # Update tracker and get vehicles that crossed the line
            vehicles_to_count = tracker.update(vehicles, counting_line)
            
            # Count vehicles that crossed the line
            for vehicle_id, direction in vehicles_to_count:
                vehicle_count += 1
                if direction == "northbound":
                    count_northbound += 1
                elif direction == "southbound":
                    count_southbound += 1
                    
                logging.info(f"Vehicle {vehicle_id} detected! Direction: {direction}, Count: {vehicle_count}")
                
                # Record detection in database
                db.add_vehicle_detection(timestamp=time.time(), direction=direction)
            
            # Draw counting line
            if args.display or args.record:
                cv2.line(frame, counting_line[0], counting_line[1], (0, 0, 255), 2)
            
            # Draw bounding boxes for all detected vehicles
            if args.display or args.record:
                for vehicle in vehicles:
                    x1, y1, x2, y2 = map(int, vehicle[:4])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # Draw tracked vehicles with IDs
                for tracked_vehicle in tracker.get_active_tracks():
                    x1, y1, x2, y2 = tracked_vehicle.bbox
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