#!/usr/bin/env python3
"""
Test script for camera setup.
This utility helps verify that the camera is working properly.

Usage:
    python tools/test_camera.py --device 0
"""

import argparse
import cv2
import time
import os
import sys

# Add project directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Main function for camera testing."""
    parser = argparse.ArgumentParser(description='Test camera setup')
    parser.add_argument('--device', type=int, default=0,
                       help='Camera device ID (default: 0)')
    parser.add_argument('--resolution', type=str, default='1280x720',
                       help='Resolution in format WIDTHxHEIGHT (default: 1280x720)')
    parser.add_argument('--fps', type=int, default=30,
                       help='Target frames per second (default: 30)')
    args = parser.parse_args()
    
    # Parse resolution
    try:
        width, height = map(int, args.resolution.split('x'))
    except ValueError:
        print(f"Invalid resolution format: {args.resolution}, using default 1280x720")
        width, height = 1280, 720
    
    print(f"Testing camera with device ID {args.device}, resolution {width}x{height}, FPS {args.fps}")
    
    # Initialize camera
    cap = cv2.VideoCapture(args.device)
    
    if not cap.isOpened():
        print(f"ERROR: Failed to open camera device {args.device}")
        return 1
    
    # Set camera properties
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)
    
    # Verify settings
    actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Actual camera settings:")
    print(f"  Resolution: {actual_width}x{actual_height}")
    print(f"  FPS: {actual_fps}")
    
    # Test frame capture
    print("Capturing frames. Press 'q' to quit.")
    
    start_time = time.time()
    frame_count = 0
    
    while True:
        # Read frame
        ret, frame = cap.read()
        
        if not ret:
            print("ERROR: Failed to read frame")
            break
        
        # Calculate FPS
        frame_count += 1
        elapsed_time = time.time() - start_time
        
        if elapsed_time >= 1.0:
            fps = frame_count / elapsed_time
            print(f"Current FPS: {fps:.2f}")
            start_time = time.time()
            frame_count = 0
        
        # Display frame
        cv2.putText(
            frame,
            f"Resolution: {int(actual_width)}x{int(actual_height)}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )
        
        cv2.imshow('Camera Test', frame)
        
        # Check for quit
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break