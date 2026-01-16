# Hailo AI HAT+ Setup Guide

**Target:** Raspberry Pi 5 + AI HAT+ (Hailo-8L NPU)  
**Purpose:** Hardware-accelerated YOLO inference for traffic monitoring  
**Performance:** 15-25 FPS @ 640x640 (vs 3-5 FPS CPU-only)

---

## Table of Contents

1. [Hardware Requirements](#hardware-requirements)
2. [Software Installation](#software-installation)
3. [Model Compilation](#model-compilation)
4. [Configuration](#configuration)
5. [Verification](#verification)
6. [Performance Tuning](#performance-tuning)
7. [Troubleshooting](#troubleshooting)

---

## Hardware Requirements

### Confirmed Working Hardware

- **Raspberry Pi 5** (8GB RAM recommended, 4GB minimum)
- **AI HAT+** (Hailo-8L, 13 TOPS)
- **Active cooling** (essential - Hailo runs hot under continuous load)
- **Stable power supply** (official Pi 5 power supply, 5V/5A minimum)
- **High-endurance microSD** (32GB minimum for model storage)

### Thermal Considerations

⚠️ **Critical:** Hailo-8L generates significant heat under continuous inference.

**Requirements:**
- Active fan cooling (min 30mm, PWM-controlled recommended)
- Thermal pad between HAT and heatsink
- Adequate airflow around Pi enclosure
- Monitor CPU temp: must stay < 70°C sustained

**Symptoms of thermal throttling:**
- Sudden FPS drops
- Inference timeouts
- System warnings in logs

---

## Software Installation

### Step 1: Update Raspberry Pi OS

```bash
# Ensure you're running latest Raspberry Pi OS (Bookworm or later)
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

### Step 2: Install Hailo Software

```bash
# Install Hailo drivers and runtime
sudo apt install hailo-all -y

# Verify installation
hailortcli fw-control identify
# Expected output: Hailo-8L device info
```

### Step 3: Install Python Dependencies

```bash
cd ~/traffic-monitor
source .venv/bin/activate

# Hailo Python bindings are installed via system package
# Verify availability:
python -c "from hailo_platform import VDevice; print('Hailo Python bindings OK')"
```

---

## Model Compilation

YOLOv8 models must be compiled to HEF (Hailo Executable Format) before use.

### Option 1: Download Pre-compiled Model (Recommended)

```bash
# Create artifacts directory
mkdir -p data/artifacts

# Download pre-compiled YOLOv8s HEF (TODO: Add download link when available)
# wget https://github.com/YOUR_REPO/releases/download/v1.0/yolov8s_hailo.hef \
#   -O data/artifacts/yolov8s.hef
```

**Pre-compiled models:**
- `yolov8n.hef` - Nano (fastest, 20-25 FPS)
- `yolov8s.hef` - Small (balanced, 15-20 FPS) **← Recommended**
- `yolov8m.hef` - Medium (slower, 10-15 FPS)

### Option 2: Compile Model Yourself

⚠️ **Advanced:** Requires Hailo Dataflow Compiler (runs on x86 Linux, not on Pi)

**Requirements:**
- x86 Linux machine (Ubuntu 20.04/22.04)
- Hailo Dataflow Compiler SDK (free account required)
- Docker (recommended for compilation environment)

**Compilation steps:**

1. **Install Hailo Dataflow Compiler:**
   ```bash
   # On x86 Linux machine (not Pi)
   # Register at https://hailo.ai/developer-zone/
   # Download Hailo Dataflow Compiler SDK
   
   # Install dependencies
   sudo apt install docker.io
   
   # Pull Hailo Docker image
   docker pull hailo/hailo_sw_suite:latest
   ```

2. **Export YOLOv8 to ONNX:**
   ```bash
   # On dev machine with Ultralytics installed
   python << EOF
   from ultralytics import YOLO
   
   # Load YOLOv8 model
   model = YOLO('yolov8s.pt')
   
   # Export to ONNX (required for Hailo)
   model.export(
       format='onnx',
       imgsz=640,
       simplify=True,
       opset=11
   )
   EOF
   # Output: yolov8s.onnx
   ```

3. **Compile ONNX to HEF:**
   ```bash
   # Run Hailo Dataflow Compiler in Docker
   docker run --rm -v $(pwd):/workspace hailo/hailo_sw_suite:latest \
     hailo parser onnx \
       --input-shape 1,3,640,640 \
       --output-dir /workspace \
       yolov8s.onnx
   
   docker run --rm -v $(pwd):/workspace hailo/hailo_sw_suite:latest \
     hailo compiler \
       --hw-arch hailo8l \
       --output-dir /workspace \
       yolov8s.har
   
   # Output: yolov8s.hef
   ```

4. **Transfer HEF to Pi:**
   ```bash
   scp yolov8s.hef pi@traffic-pi.local:~/traffic-monitor/data/artifacts/
   ```

**Compilation notes:**
- Input shape must be fixed (e.g., 640x640)
- Quantization may slightly affect accuracy (test with validation set)
- Compilation takes 30-60 minutes depending on model size
- HEF files are hardware-specific (Hailo-8L vs Hailo-8)

---

## Configuration

### Step 1: Update config.yaml

```bash
cd ~/traffic-monitor
nano config/config.yaml
```

**Configure Hailo backend:**

```yaml
# config/config.yaml

detection:
  backend: "hailo"  # Use Hailo NPU instead of CPU/GPU
  
  hailo:
    # Path to compiled HEF model
    hef_path: "data/artifacts/yolov8s.hef"
    
    # Model input dimensions (must match HEF compilation)
    input_size: [640, 640]
    
    # Detection thresholds (same as YOLO backend)
    conf_threshold: 0.25
    iou_threshold: 0.45
    
    # Classes to detect (COCO IDs)
    classes: [0, 1, 2, 3, 5, 7]  # person, bicycle, car, motorcycle, bus, truck
    
    # Class-specific confidence thresholds
    class_thresholds:
      0: 0.20   # person (low threshold for safety)
      1: 0.25   # bicycle
      2: 0.40   # car (high threshold, easy to detect)
      3: 0.30   # motorcycle
      5: 0.45   # bus
      7: 0.45   # truck

camera:
  backend: "picamera2"  # Use Pi Camera (or "opencv" for USB)
  resolution: [1280, 720]
  fps: 20  # Target 20 FPS (Hailo can sustain this)
```

### Step 2: Verify Configuration

```bash
python src/main.py --config config/config.yaml --stop  # Stop any running instance
python src/main.py --config config/config.yaml
```

**Check logs for:**
```
INFO: Loading Hailo model from: data/artifacts/yolov8s.hef
INFO: Hailo backend initialized: yolov8s_input
INFO: Hailo input shape: (1, 3, 640, 640)
INFO: Hailo inference device: Hailo-8 NPU (AI HAT+)
INFO: Target FPS: 15-25 @ 640x640
```

---

## Verification

### Test 1: Inference Functionality

```bash
# Run system for 1 minute, check logs
python src/main.py --config config/config.yaml &
sleep 60
curl http://localhost:5000/api/status | jq

# Expected output:
# - "running": true
# - "fps_capture": 15-25
# - No errors in logs
```

### Test 2: Detection Accuracy

Compare Hailo detections vs GPU YOLO baseline:

```bash
# Save 10-minute validation clip on dev machine with GPU
python src/main.py --config config/config.yaml --record

# Run same clip on Pi with Hailo
python src/main.py --config config/config.yaml --source validation.mp4

# Compare count_events
sqlite3 data/database.sqlite << EOF
SELECT direction_code, COUNT(*) as count 
FROM count_events 
WHERE ts > strftime('%s', 'now', '-10 minutes') * 1000
GROUP BY direction_code;
EOF

# Target: < 5% count difference vs GPU baseline
```

### Test 3: Thermal Performance

```bash
# Monitor CPU temperature during inference
watch -n 5 'vcgencmd measure_temp'

# Run system for 1 hour, ensure temp stays < 70°C
# If temp > 75°C: Add more cooling or reduce FPS
```

### Test 4: 24-Hour Stability

```bash
# Enable systemd service
sudo systemctl enable traffic-monitor
sudo systemctl start traffic-monitor

# Monitor for 24 hours
sudo journalctl -u traffic-monitor -f

# Check for:
# - No crashes or restarts
# - Consistent FPS (no drift)
# - No memory leaks (check with 'free -h')
# - Temperature stable
```

---

## Performance Tuning

### FPS Optimization

**Current FPS too low?**

1. **Reduce resolution:**
   ```yaml
   camera:
     resolution: [960, 540]  # Down from 1280x720
   ```

2. **Use smaller model:**
   ```yaml
   hailo:
     hef_path: "data/artifacts/yolov8n.hef"  # Nano model (faster)
   ```

3. **Reduce camera FPS:**
   ```yaml
   camera:
     fps: 15  # Down from 20
   ```

4. **Optimize preprocessing:**
   - Letterbox resize is fast (already implemented)
   - Consider ROI cropping in future

### Thermal Management

**Temperature > 70°C?**

1. **Improve cooling:**
   - Upgrade to larger fan (40mm recommended)
   - Add heatsinks to Pi CPU
   - Ensure good airflow in enclosure

2. **Reduce workload:**
   - Lower FPS: `camera.fps: 15`
   - Frame skipping: Process every 2nd frame
   - Smaller model: yolov8n.hef

3. **Power management:**
   ```bash
   # Check power supply is adequate (5V/5A)
   vcgencmd get_throttled
   # 0x0 = OK, anything else = power issue
   ```

### Speed Measurement Considerations

For accurate speed measurement (future milestone):

**Requirements:**
- Consistent frame rate (≥ 15 FPS, no drops)
- Accurate timestamps from camera (not processing time)
- Minimal inference jitter

**Recommendations:**
- Lock camera FPS: `camera.fps: 20`
- Monitor FPS variance (should be < 5%)
- Consider frame buffering if needed

---

## Troubleshooting

### Problem: "HailoRT Python bindings not found"

**Cause:** `hailo-all` package not installed

**Solution:**
```bash
sudo apt install hailo-all -y
# Reboot if needed
sudo reboot
```

### Problem: "Hailo HEF model not found"

**Cause:** Missing or incorrect HEF file path

**Solution:**
```bash
# Check file exists
ls -lh data/artifacts/yolov8s.hef

# If missing, download or compile (see Model Compilation section)

# Verify path in config
grep hef_path config/config.yaml
```

### Problem: "Failed to initialize Hailo backend"

**Cause:** HAT not detected or driver issue

**Solution:**
```bash
# Check HAT connection
hailortcli fw-control identify

# Expected: Device info displayed
# If error: Check HAT is seated properly, reboot Pi

# Check kernel modules
lsmod | grep hailo

# If empty: Driver not loaded
sudo modprobe hailo_pci
```

### Problem: Low FPS (< 10 FPS)

**Possible causes:**

1. **Thermal throttling:**
   ```bash
   vcgencmd measure_temp
   # If > 70°C: Add cooling
   ```

2. **Camera bottleneck:**
   ```bash
   # Check capture FPS vs inference FPS in logs
   # If capture FPS low: Camera issue (not Hailo)
   ```

3. **Wrong model size:**
   ```bash
   # Check model file size
   ls -lh data/artifacts/*.hef
   # yolov8n: ~10MB, yolov8s: ~25MB, yolov8m: ~50MB
   # Larger = slower
   ```

4. **Post-processing overhead:**
   ```python
   # Check inference time in logs
   # "Hailo inference: X FPS"
   # If low: Post-processing bottleneck (contact maintainer)
   ```

### Problem: Incorrect detections vs GPU baseline

**Cause:** Quantization effects from HEF compilation

**Solution:**

1. **Adjust confidence thresholds:**
   ```yaml
   hailo:
     conf_threshold: 0.30  # Increase from 0.25
     class_thresholds:
       0: 0.25  # Adjust per-class
   ```

2. **Validate with test clips:**
   - Run same clip on GPU and Hailo
   - Compare detection counts
   - Fine-tune thresholds until < 5% difference

3. **Re-compile HEF with different quantization:**
   - Use calibration dataset during compilation
   - See Hailo Dataflow Compiler docs

### Problem: System falls back to CPU YOLO

**Cause:** Hailo initialization failed, auto-fallback triggered

**Check logs:**
```bash
journalctl -u traffic-monitor | grep -i hailo
# Look for error messages
```

**Common causes:**
- HEF file corrupted (re-download)
- Incompatible HEF (compiled for Hailo-8, not Hailo-8L)
- HAT disconnected (reseat HAT)

---

## Performance Expectations

### Benchmark Results (Pi 5 + AI HAT+)

| Model | Resolution | FPS | Accuracy | Use Case |
|-------|-----------|-----|----------|----------|
| YOLOv8n | 640x640 | 20-25 | Good | Fast tracking, < 30 mph roads |
| YOLOv8s | 640x640 | 15-20 | Excellent | **Recommended** - balanced |
| YOLOv8m | 640x640 | 10-15 | Best | Low-speed, high-accuracy needs |

**Thermal performance:**
- Ambient 20°C, fan cooling: 55-65°C sustained ✅
- Ambient 20°C, passive: 70-80°C (thermal throttling) ⚠️
- Ambient 30°C, fan cooling: 65-75°C (acceptable) ⚠️

**Power consumption:**
- Pi 5 + HAT + Camera: ~15W peak
- Recommended power supply: 5V/5A (25W)

### Comparison: Hailo vs CPU YOLO

| Metric | Hailo (AI HAT+) | CPU (Pi 5) | GPU (CUDA) |
|--------|----------------|------------|------------|
| FPS @ 640x640 | 15-20 | 3-5 | 60-120 |
| Power (W) | 15 | 10 | 300+ |
| Cost | $70 HAT | $0 | $400+ GPU |
| Accuracy | ~95% of GPU | Same | Baseline |
| Portability | Excellent | Excellent | Poor |

---

## Next Steps

After Hailo backend is working:

1. **Run 72-hour stability test**
2. **Validate counting accuracy** (see DEPLOYMENT.md)
3. **Tune for your camera angle/lighting**
4. **Deploy to field location**
5. **Implement speed measurement** (Milestone 3)

---

## Support

**Issues with Hailo setup?**

1. Check logs: `sudo journalctl -u traffic-monitor -n 100`
2. Verify hardware: `hailortcli fw-control identify`
3. Test with example: `hailortcli run yolov8s.hef`
4. Open GitHub issue with logs

**Resources:**
- [Hailo AI Developer Zone](https://hailo.ai/developer-zone/)
- [Raspberry Pi AI HAT+ Docs](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html)
- [YOLOv8 Ultralytics Docs](https://docs.ultralytics.com/)

---

**Document Version:** 1.0  
**Last Updated:** January 16, 2026  
**Tested On:** Raspberry Pi 5 (8GB) + AI HAT+ + Camera Module 3
