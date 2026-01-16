#!/usr/bin/env python3
"""
Hailo AI HAT+ diagnostic script.

Tests Hailo hardware, drivers, and model loading without running the full system.
Use this to verify Hailo setup before deploying traffic monitor.

Usage:
    python tools/test_hailo.py
    python tools/test_hailo.py --hef data/artifacts/yolov8s.hef
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def test_hailo_drivers():
    """Test if Hailo drivers are installed and working."""
    print("=" * 70)
    print("TEST 1: Hailo Drivers & Hardware")
    print("=" * 70)
    
    try:
        from hailo_platform import VDevice
        print("✓ hailo_platform module imported successfully")
        
        # Try to create VDevice (detects Hailo hardware)
        params = VDevice.create_params()
        device = VDevice(params)
        print(f"✓ Hailo device detected: {device}")
        
        # Get device info
        device_info = device.get_device_info()
        print(f"  Device architecture: {device_info.device_architecture}")
        print(f"  Device ID: {device_info.device_id}")
        
        print("\n✓✓ Hailo hardware test PASSED\n")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import hailo_platform: {e}")
        print("  Install with: sudo apt install hailo-all")
        print("\n✗✗ Hailo hardware test FAILED\n")
        return False
    except Exception as e:
        print(f"✗ Failed to detect Hailo device: {e}")
        print("  Possible causes:")
        print("  - AI HAT+ not properly seated")
        print("  - Driver not loaded (try: sudo modprobe hailo_pci)")
        print("  - Reboot required after hailo-all installation")
        print("\n✗✗ Hailo hardware test FAILED\n")
        return False


def test_hef_loading(hef_path: str):
    """Test if HEF model can be loaded."""
    print("=" * 70)
    print("TEST 2: HEF Model Loading")
    print("=" * 70)
    
    if not Path(hef_path).exists():
        print(f"✗ HEF file not found: {hef_path}")
        print("  Download or compile a YOLOv8 HEF model")
        print("  See docs/HAILO_SETUP.md for instructions")
        print("\n✗✗ HEF loading test SKIPPED\n")
        return False
    
    print(f"Loading HEF from: {hef_path}")
    print(f"File size: {Path(hef_path).stat().st_size / 1024 / 1024:.1f} MB")
    
    try:
        from hailo_platform import VDevice, ConfigureParams
        
        params = VDevice.create_params()
        device = VDevice(params)
        
        # Configure device with HEF
        network_groups = device.configure(
            hef_path,
            ConfigureParams.create_from_network_group()
        )
        
        print(f"✓ HEF loaded successfully")
        print(f"  Network groups: {len(network_groups)}")
        
        network_group = network_groups[0]
        input_vstreams = network_group.get_input_vstream_infos()
        output_vstreams = network_group.get_output_vstream_infos()
        
        print(f"  Input streams: {len(input_vstreams)}")
        for i, vstream in enumerate(input_vstreams):
            print(f"    [{i}] {vstream.name}: {vstream.shape}")
        
        print(f"  Output streams: {len(output_vstreams)}")
        for i, vstream in enumerate(output_vstreams):
            print(f"    [{i}] {vstream.name}: {vstream.shape}")
        
        print("\n✓✓ HEF loading test PASSED\n")
        return True
        
    except FileNotFoundError as e:
        print(f"✗ HEF file error: {e}")
        print("\n✗✗ HEF loading test FAILED\n")
        return False
    except Exception as e:
        print(f"✗ Failed to load HEF: {e}")
        print("  Possible causes:")
        print("  - HEF compiled for wrong Hailo architecture (Hailo-8 vs Hailo-8L)")
        print("  - Corrupted HEF file (re-download or re-compile)")
        print("\n✗✗ HEF loading test FAILED\n")
        return False


def test_inference(hef_path: str):
    """Test inference with dummy frame."""
    print("=" * 70)
    print("TEST 3: Inference Performance")
    print("=" * 70)
    
    if not Path(hef_path).exists():
        print("✗ HEF file not found, skipping inference test")
        print("\n✗✗ Inference test SKIPPED\n")
        return False
    
    try:
        from hailo_platform import VDevice, ConfigureParams, InferVStreams
        
        # Setup device and model
        params = VDevice.create_params()
        device = VDevice(params)
        network_groups = device.configure(
            hef_path,
            ConfigureParams.create_from_network_group()
        )
        network_group = network_groups[0]
        
        # Get stream info
        input_vstream_info = network_group.get_input_vstream_infos()[0]
        input_shape = input_vstream_info.shape
        
        print(f"Model input shape: {input_shape}")
        
        # Create dummy input frame
        # Expected: (batch, channels, height, width) or (batch, height, width, channels)
        if len(input_shape) == 4:
            batch, channels, height, width = input_shape
            dummy_frame = np.random.rand(batch, channels, height, width).astype(np.float32)
        else:
            print(f"✗ Unexpected input shape: {input_shape}")
            return False
        
        print(f"Created dummy frame: {dummy_frame.shape}")
        
        # Run inference benchmark
        network_group_params = network_group.create_params()
        input_vstreams_params = network_group_params.input_vstreams_params
        output_vstreams_params = network_group_params.output_vstreams_params
        
        num_warmup = 10
        num_benchmark = 100
        
        print(f"\nWarm-up: Running {num_warmup} inferences...")
        with InferVStreams(network_group, input_vstreams_params, output_vstreams_params) as infer_pipeline:
            with network_group.activate(network_group_params):
                # Warm-up
                for i in range(num_warmup):
                    input_data = {input_vstream_info.name: dummy_frame}
                    _ = infer_pipeline.infer(input_data)
                
                # Benchmark
                print(f"Benchmark: Running {num_benchmark} inferences...")
                start_time = time.perf_counter()
                
                for i in range(num_benchmark):
                    input_data = {input_vstream_info.name: dummy_frame}
                    outputs = infer_pipeline.infer(input_data)
                
                elapsed = time.perf_counter() - start_time
        
        # Calculate metrics
        avg_inference_time = (elapsed / num_benchmark) * 1000  # ms
        fps = num_benchmark / elapsed
        
        print(f"\n✓ Inference completed successfully")
        print(f"  Average inference time: {avg_inference_time:.1f} ms")
        print(f"  Throughput: {fps:.1f} FPS")
        
        # Check performance
        if fps < 10:
            print("  ⚠ WARNING: FPS below target (< 10 FPS)")
            print("    Check cooling, use smaller model, or reduce resolution")
        elif fps < 15:
            print("  ⚠ NOTICE: FPS marginal (10-15 FPS)")
            print("    Consider using yolov8n.hef for better performance")
        else:
            print(f"  ✓ FPS acceptable (≥ 15 FPS)")
        
        print("\n✓✓ Inference test PASSED\n")
        return True
        
    except Exception as e:
        print(f"✗ Inference failed: {e}")
        print("\n✗✗ Inference test FAILED\n")
        return False


def test_temperature():
    """Check CPU temperature (thermal management)."""
    print("=" * 70)
    print("TEST 4: Thermal Check")
    print("=" * 70)
    
    try:
        import subprocess
        result = subprocess.run(
            ['vcgencmd', 'measure_temp'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            temp_str = result.stdout.strip()
            # Parse: "temp=45.0'C"
            temp_c = float(temp_str.split('=')[1].split("'")[0])
            
            print(f"Current CPU temperature: {temp_c:.1f}°C")
            
            if temp_c < 60:
                print("  ✓ Temperature excellent (< 60°C)")
            elif temp_c < 70:
                print("  ✓ Temperature good (60-70°C)")
            elif temp_c < 80:
                print("  ⚠ Temperature high (70-80°C) - monitor during inference")
            else:
                print("  ✗ Temperature critical (> 80°C) - add cooling immediately")
            
            print("\n✓✓ Thermal check PASSED\n")
            return True
        else:
            print("✗ Could not read temperature (vcgencmd failed)")
            print("  Not critical - continue with deployment")
            print("\n⚠ Thermal check SKIPPED\n")
            return True
            
    except Exception as e:
        print(f"⚠ Thermal check failed: {e}")
        print("  Not critical on non-Pi systems")
        print("\n⚠ Thermal check SKIPPED\n")
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Test Hailo AI HAT+ setup',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/test_hailo.py
  python tools/test_hailo.py --hef data/artifacts/yolov8s.hef
  
This script runs 4 tests:
  1. Hailo drivers and hardware detection
  2. HEF model loading
  3. Inference performance benchmark
  4. Thermal check

Pass all tests before deploying traffic monitor with Hailo backend.
        """
    )
    
    parser.add_argument(
        '--hef',
        default='data/artifacts/yolov8s.hef',
        help='Path to HEF model file (default: data/artifacts/yolov8s.hef)'
    )
    
    args = parser.parse_args()
    
    print("\n")
    print("=" * 70)
    print("Hailo AI HAT+ Diagnostic Test")
    print("=" * 70)
    print(f"HEF path: {args.hef}")
    print("\n")
    
    # Run tests
    results = []
    
    results.append(("Hailo Drivers", test_hailo_drivers()))
    
    if results[-1][1]:  # Only continue if drivers work
        results.append(("HEF Loading", test_hef_loading(args.hef)))
        
        if results[-1][1]:  # Only test inference if HEF loads
            results.append(("Inference", test_inference(args.hef)))
    
    results.append(("Thermal", test_temperature()))
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:20s}: {status}")
    
    print("=" * 70)
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("\nYour Hailo setup is ready for deployment!")
        print("Next steps:")
        print("  1. Update config/config.yaml with detection.backend='hailo'")
        print("  2. Run: python src/main.py --config config/config.yaml")
        print("  3. Monitor FPS and temperature during first hour")
        print()
        return 0
    else:
        print("\n✗✗✗ SOME TESTS FAILED ✗✗✗")
        print("\nPlease fix issues before deploying with Hailo backend.")
        print("See docs/HAILO_SETUP.md for troubleshooting.")
        print()
        return 1


if __name__ == '__main__':
    sys.exit(main())
