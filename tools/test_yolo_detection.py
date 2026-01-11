#!/usr/bin/env python3
"""
Test script for YOLO detection with GPU support.

This utility helps verify that:
1. Ultralytics YOLO is installed correctly
2. GPU/CUDA is being used (if available)
3. Detection and class filtering work as expected

Usage:
    python tools/test_yolo_detection.py --device 0
    python tools/test_yolo_detection.py --video path/to/video.mp4
    python tools/test_yolo_detection.py --image path/to/image.jpg
"""

import argparse
import os
import sys
import time

# Add project directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import cv2
import numpy as np


def check_gpu_availability():
    """Check if CUDA/GPU is available for PyTorch."""
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f"✅ CUDA available: {gpu_name} ({gpu_memory:.1f} GB)")
            return True
        else:
            print("⚠️  CUDA not available - running on CPU")
            return False
    except ImportError:
        print("⚠️  PyTorch not installed - cannot check GPU")
        return False


def test_yolo_detection(source, model_name="yolov8s.pt", classes=None, conf_threshold=0.35):
    """
    Test YOLO detection on a video/camera/image source.
    
    Args:
        source: Camera device ID (int), video path, or image path
        model_name: YOLO model to use
        classes: List of class IDs to detect (None = all)
        conf_threshold: Confidence threshold
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        print("❌ Ultralytics not installed!")
        print("   Install with: pip install ultralytics")
        return 1
    
    # Check GPU
    check_gpu_availability()
    
    # Load model
    print(f"\n📦 Loading model: {model_name}")
    start = time.time()
    model = YOLO(model_name)
    print(f"   Model loaded in {time.time() - start:.2f}s")
    
    # Class names from COCO
    class_names = {
        0: "person", 1: "bicycle", 2: "car", 3: "motorcycle",
        5: "bus", 7: "truck"
    }
    
    # Default: neighborhood traffic classes
    if classes is None:
        classes = [0, 1, 2, 3, 5, 7]
    
    print(f"   Detecting classes: {[class_names.get(c, c) for c in classes]}")
    print(f"   Confidence threshold: {conf_threshold}")
    
    # Determine source type
    is_image = isinstance(source, str) and source.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))
    
    if is_image:
        # Single image mode
        print(f"\n🖼️  Processing image: {source}")
        frame = cv2.imread(source)
        if frame is None:
            print(f"❌ Failed to load image: {source}")
            return 1
        
        # Run detection
        results = model.predict(
            source=frame,
            conf=conf_threshold,
            classes=classes,
            verbose=False
        )
        
        # Draw results
        annotated = draw_detections(frame, results[0], class_names)
        
        # Show and save
        cv2.imshow("YOLO Detection", annotated)
        output_path = source.rsplit('.', 1)[0] + "_detected.jpg"
        cv2.imwrite(output_path, annotated)
        print(f"   Saved result to: {output_path}")
        print("   Press any key to close...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
    else:
        # Video/camera mode
        if isinstance(source, int):
            print(f"\n📷 Opening camera device: {source}")
            cap = cv2.VideoCapture(source)
        else:
            print(f"\n🎬 Opening video: {source}")
            cap = cv2.VideoCapture(source)
        
        if not cap.isOpened():
            print(f"❌ Failed to open source: {source}")
            return 1
        
        # Get video properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps_source = cap.get(cv2.CAP_PROP_FPS) or 30
        print(f"   Source: {width}x{height} @ {fps_source:.1f} FPS")
        
        print("\n🔍 Running detection... Press 'q' to quit\n")
        
        # FPS tracking
        frame_times = []
        frame_count = 0
        detection_counts = {c: 0 for c in classes}
        
        while True:
            ret, frame = cap.read()
            if not ret:
                if isinstance(source, int):
                    print("Frame read failed")
                    continue
                else:
                    print("End of video")
                    break
            
            frame_count += 1
            start_time = time.time()
            
            # Run detection
            results = model.predict(
                source=frame,
                conf=conf_threshold,
                classes=classes,
                verbose=False
            )
            
            inference_time = time.time() - start_time
            frame_times.append(inference_time)
            
            # Keep only last 30 frame times for rolling average
            if len(frame_times) > 30:
                frame_times.pop(0)
            
            avg_fps = 1.0 / (sum(frame_times) / len(frame_times))
            
            # Count detections by class
            if results[0].boxes is not None:
                for box in results[0].boxes:
                    cls_id = int(box.cls[0])
                    if cls_id in detection_counts:
                        detection_counts[cls_id] += 1
            
            # Draw results
            annotated = draw_detections(frame, results[0], class_names)
            
            # Add FPS overlay
            cv2.putText(
                annotated,
                f"FPS: {avg_fps:.1f} | Inference: {inference_time*1000:.1f}ms",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            
            cv2.imshow("YOLO Detection Test", annotated)
            
            # Print stats every 30 frames
            if frame_count % 30 == 0:
                print(f"Frame {frame_count}: FPS={avg_fps:.1f}, Inference={inference_time*1000:.1f}ms")
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        # Print summary
        print("\n" + "="*50)
        print("📊 Detection Summary")
        print("="*50)
        print(f"Frames processed: {frame_count}")
        print(f"Average FPS: {avg_fps:.1f}")
        print(f"Average inference time: {sum(frame_times)/len(frame_times)*1000:.1f}ms")
        print("\nDetections by class:")
        for cls_id, count in detection_counts.items():
            name = class_names.get(cls_id, f"class_{cls_id}")
            print(f"  {name}: {count}")
    
    return 0


def draw_detections(frame, result, class_names):
    """Draw bounding boxes and labels on frame."""
    annotated = frame.copy()
    
    if result.boxes is None:
        return annotated
    
    boxes = result.boxes
    for i, box in enumerate(boxes):
        # Get box coordinates
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        cls_id = int(box.cls[0])
        
        # Color by class
        colors = {
            0: (255, 0, 255),    # person - magenta
            1: (0, 255, 255),    # bicycle - yellow
            2: (0, 255, 0),      # car - green
            3: (0, 165, 255),    # motorcycle - orange
            5: (255, 0, 0),      # bus - blue
            7: (0, 0, 255),      # truck - red
        }
        color = colors.get(cls_id, (128, 128, 128))
        
        # Draw box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        
        # Draw label
        label = f"{class_names.get(cls_id, cls_id)}: {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
        cv2.putText(annotated, label, (x1 + 2, y1 - 4),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    return annotated


def main():
    parser = argparse.ArgumentParser(
        description='Test YOLO detection with GPU support',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with webcam
  python tools/test_yolo_detection.py --device 0
  
  # Test with video file
  python tools/test_yolo_detection.py --video traffic_sample.mp4
  
  # Test with image
  python tools/test_yolo_detection.py --image street_photo.jpg
  
  # Use different model
  python tools/test_yolo_detection.py --device 0 --model yolov8n.pt
  
  # Detect only vehicles (no pedestrians)
  python tools/test_yolo_detection.py --device 0 --classes 2 3 5 7
"""
    )
    
    # Source options (mutually exclusive)
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument('--device', type=int, default=0,
                             help='Camera device ID (default: 0)')
    source_group.add_argument('--video', type=str,
                             help='Path to video file')
    source_group.add_argument('--image', type=str,
                             help='Path to image file')
    
    # Detection options
    parser.add_argument('--model', type=str, default='yolov8s.pt',
                       help='YOLO model name or path (default: yolov8s.pt)')
    parser.add_argument('--conf', type=float, default=0.35,
                       help='Confidence threshold (default: 0.35)')
    parser.add_argument('--classes', type=int, nargs='+',
                       help='Class IDs to detect (default: 0,1,2,3,5,7 = people+vehicles)')
    
    args = parser.parse_args()
    
    print("="*50)
    print("🚗 YOLO Detection Test")
    print("="*50)
    
    # Determine source
    if args.video:
        source = args.video
    elif args.image:
        source = args.image
    else:
        source = args.device
    
    return test_yolo_detection(
        source=source,
        model_name=args.model,
        classes=args.classes,
        conf_threshold=args.conf
    )


if __name__ == "__main__":
    sys.exit(main())

