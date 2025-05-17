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

# Import local modules
from camera.capture import VideoCapture
from detection.vehicle import VehicleDetector
from storage.database import Database
from cloud.sync import CloudSync
from cloud.utils import check_cloud_config

def load_config(config_path):
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        sys.exit(1)

def setup_logging(log_path, log_level):
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
            fps=config['camera']['fps']
        )
        
        # Initialize vehicle detector
        detector = VehicleDetector(
            min_contour_area=config['detection']['min_contour_area'],
            detect_shadows=config['detection']['detect_shadows']
        )
        
        # Initialize counters
        vehicle_count = 0
        frame_count = 0
        last_count_time = time.time()
        
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
        
        # Define counting line (horizontal line at the middle of the frame)
        line_position = config['detection']['counting_line_position']
        
        # Main processing loop
        while True:
            # Read frame from camera
            ret, frame = camera.read()
            if not ret:
                logging.error("Failed to read frame")
                break
            
            # Process frame for vehicle detection
            vehicles = detector.detect(frame)
            
            # Count vehicles crossing the line
            frame_height = frame.shape[0]
            counting_line_y = int(frame_height * line_position)
            
            # Draw counting line
            if args.display or args.record:
                cv2.line(frame, (0, counting_line_y), (frame.shape[1], counting_line_y), (0, 0, 255), 2)
            
            # Check if vehicles are crossing the line
            for vehicle in vehicles:
                x1, y1, x2, y2 = map(int, vehicle[:4])
                vehicle_center_y = (y1 + y2) // 2
                
                # Check if vehicle is crossing the line (from top to bottom)
                if abs(vehicle_center_y - counting_line_y) < 5:
                    vehicle_count += 1
                    logging.info(f"Vehicle detected! Count: {vehicle_count}")
                    
                    # Determine direction
                    if y2 - y1 > 0:  # Height is positive, so likely going down
                        direction = "southbound"
                    else:
                        direction = "northbound"
                    
                    # Record detection in database
                    db.add_vehicle_detection(timestamp=time.time(), direction=direction)
                
                # Draw bounding box
                if args.display or args.record:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Display vehicle count
            if args.display or args.record:
                cv2.putText(
                    frame,
                    f"Vehicle Count: {vehicle_count}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
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