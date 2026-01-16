# Raspberry Pi 5 + Hailo Quick Start

**Your Pi:** `traffic-pi` (accessible via SSH on local network)  
**Goal:** Deploy traffic monitor with Hailo AI HAT+ acceleration  
**Time:** 30 minutes (assuming HEF model ready)

---

## Prerequisites

- [x] Raspberry Pi 5 + AI HAT+ accessible via SSH
- [ ] HEF model file (`yolov8s.hef` or similar)
- [ ] Active cooling on Pi (fan running)

---

## Step 1: Transfer Code to Pi

```bash
# On your Windows machine
cd "c:\Users\Michael\workspace\Coding Projects\traffic-monitor"

# Option A: Push via git (if Pi has git access)
git add .
git commit -m "Add Hailo backend implementation"
git push

# Then on Pi:
ssh pi@traffic-pi.local
cd ~/traffic-monitor
git pull

# Option B: Direct transfer via SCP
scp -r . pi@traffic-pi.local:~/traffic-monitor/
```

---

## Step 2: Transfer HEF Model (If You Have One)

```bash
# On Windows machine
# Assuming you have yolov8s.hef downloaded
scp yolov8s.hef pi@traffic-pi.local:~/traffic-monitor/data/artifacts/

# Verify on Pi
ssh pi@traffic-pi.local
ls -lh ~/traffic-monitor/data/artifacts/yolov8s.hef
```

**If you DON'T have HEF model yet:**
- See `docs/HAILO_SETUP.md` → "Model Compilation" section
- Pre-compiled download link: [TO BE ADDED]
- Or compile yourself using Hailo Dataflow Compiler

---

## Step 3: Install Hailo Software (First Time Only)

```bash
ssh pi@traffic-pi.local

# Update system
sudo apt update
sudo apt full-upgrade -y

# Install Hailo drivers and runtime
sudo apt install hailo-all -y

# Reboot to load drivers
sudo reboot

# Wait 30 seconds, then reconnect
ssh pi@traffic-pi.local
```

---

## Step 4: Test Hailo Hardware

```bash
cd ~/traffic-monitor

# Run diagnostic tests
python tools/test_hailo.py --hef data/artifacts/yolov8s.hef

# Expected output:
# ✓✓ Hailo hardware test PASSED
# ✓✓ HEF loading test PASSED
# ✓✓ Inference test PASSED (15-25 FPS)
# ✓✓ Thermal check PASSED (< 70°C)
```

**If any test fails:**
- Check docs/HAILO_SETUP.md → "Troubleshooting"
- Common issues:
  - HAT not seated properly → reseat and reboot
  - HEF missing → download/compile model
  - No cooling → FPS low, temp high

---

## Step 5: Configure System for Hailo

```bash
cd ~/traffic-monitor

# Edit config (if not already using Hailo)
nano config/config.yaml
```

**Set these values:**

```yaml
camera:
  backend: "picamera2"  # Or "opencv" for USB camera
  resolution: [1280, 720]
  fps: 20

detection:
  backend: "hailo"  # ← Key change
  
  hailo:
    hef_path: "data/artifacts/yolov8s.hef"
    input_size: [640, 640]
    conf_threshold: 0.25
    classes: [0, 1, 2, 3, 5, 7]
    class_thresholds:
      0: 0.20  # person
      1: 0.25  # bicycle
      2: 0.40  # car
      3: 0.30  # motorcycle
      5: 0.45  # bus
      7: 0.45  # truck
```

**Save and exit:** `Ctrl+X`, `Y`, `Enter`

---

## Step 6: Test Run (Manual)

```bash
cd ~/traffic-monitor

# Stop any existing instance
python src/main.py --stop

# Start manually (keep SSH open)
python src/main.py --config config/config.yaml

# Watch for these log lines:
# INFO: Loading Hailo model from: data/artifacts/yolov8s.hef
# INFO: Hailo backend initialized
# INFO: Hailo inference device: Hailo-8 NPU (AI HAT+)
# INFO: Target FPS: 15-25 @ 640x640

# Let it run for 5 minutes, monitor:
# - FPS in logs (should be 15-25)
# - CPU temp: watch -n 5 'vcgencmd measure_temp'
# - Counts: curl http://localhost:5000/api/status | jq
```

**Stop test:** `Ctrl+C`

---

## Step 7: Deploy as Service (24/7 Operation)

```bash
cd ~/traffic-monitor

# Stop manual instance if running
python src/main.py --stop

# Start systemd service
sudo systemctl start traffic-monitor

# Check status
sudo systemctl status traffic-monitor

# Watch logs
sudo journalctl -u traffic-monitor -f

# Enable auto-start on boot
sudo systemctl enable traffic-monitor
```

---

## Step 8: Verify Operation

### Check System Status

```bash
# Health check
curl http://localhost:5000/api/health | jq

# Expected:
# - "running": true
# - "fps_capture": 15-25
# - "cpu_temp_c": < 70
# - "warnings": []

# Compact status
curl http://localhost:5000/api/status | jq

# Expected:
# - "counts_today_total": increasing
# - "last_frame_age_s": < 2
```

### Monitor Temperature

```bash
# Continuous monitoring
watch -n 5 'vcgencmd measure_temp'

# Target: < 70°C sustained
# Warning: > 70°C (add more cooling)
# Critical: > 80°C (system will throttle)
```

### Check Counts

```bash
# Wait 10-15 minutes for some traffic
# Query database
sqlite3 data/database.sqlite << EOF
SELECT 
  direction_code,
  COUNT(*) as count,
  class_name,
  COUNT(*) as class_count
FROM count_events 
WHERE ts > strftime('%s', 'now', '-1 hour') * 1000
GROUP BY direction_code, class_name
ORDER BY direction_code, class_count DESC;
EOF

# Should see counts for detected classes
```

---

## Step 9: Validation (Important!)

Run validation procedure to ensure counting accuracy:

```bash
cd ~/traffic-monitor

# 1. Record 10-minute validation clip
# (Do this during traffic hours)

# 2. Manual ground truth count:
# - Watch saved clip or live feed
# - Count vehicles manually
# - Note: direction, time, class

# 3. Compare with system counts:
sqlite3 data/database.sqlite << EOF
SELECT 
  direction_code,
  class_name,
  COUNT(*) as system_count
FROM count_events 
WHERE ts BETWEEN START_TS AND END_TS
GROUP BY direction_code, class_name;
EOF

# 4. Calculate accuracy:
# accuracy = (system_count / manual_count) * 100
# Target: ≥ 85% overall, ≥ 90% direction accuracy
```

---

## Troubleshooting

### Problem: "Hailo backend not available"

```bash
# Check logs
sudo journalctl -u traffic-monitor | grep -i hailo

# Common causes:
# 1. HEF file missing
ls -lh ~/traffic-monitor/data/artifacts/*.hef

# 2. HAT not detected
hailortcli fw-control identify

# 3. Driver not loaded
lsmod | grep hailo
# If empty: sudo modprobe hailo_pci && sudo reboot
```

### Problem: Low FPS (< 10)

```bash
# Check temperature
vcgencmd measure_temp
# If > 70°C: Thermal throttling

# Check power
vcgencmd get_throttled
# If not 0x0: Power supply issue

# Solutions:
# 1. Add/improve cooling
# 2. Use smaller model (yolov8n.hef)
# 3. Reduce camera FPS
nano config/config.yaml
# Set: camera.fps: 15
```

### Problem: System falls back to CPU

```bash
# Check which backend is actually running
curl http://localhost:5000/api/status | jq

# Check logs for fallback messages
sudo journalctl -u traffic-monitor | grep -i fallback

# If Hailo failed to initialize:
# - Check HEF path in config
# - Re-run tools/test_hailo.py
# - Check HAT connection
```

---

## Performance Expectations

| Metric | Target | Acceptable | Needs Work |
|--------|--------|------------|------------|
| FPS | 20-25 | 15-20 | < 15 |
| CPU Temp | < 60°C | 60-70°C | > 70°C |
| Accuracy | > 90% | 85-90% | < 85% |
| Uptime | 100% | > 99% | < 99% |

---

## Next Steps

After 24 hours of stable operation:

1. **Run 72-hour stability test**
   - Monitor FPS, temp, memory
   - Check for crashes, drift

2. **Validate counting accuracy**
   - 3 × 10-minute validation windows
   - Compare to GPU baseline if available

3. **Document your deployment**
   - Camera position, angle
   - Validation results
   - Any config adjustments

4. **Speed measurement (Milestone 3)**
   - Calibrate camera geometry
   - Implement speed calculation
   - Validate against known speeds

---

## Monitoring Commands (Quick Reference)

```bash
# Service status
sudo systemctl status traffic-monitor

# Live logs
sudo journalctl -u traffic-monitor -f

# Temperature
vcgencmd measure_temp

# API health
curl http://localhost:5000/api/health | jq

# Recent counts
sqlite3 data/database.sqlite "SELECT * FROM count_events ORDER BY ts DESC LIMIT 10;"

# Disk space
df -h

# Memory
free -h

# Restart service
sudo systemctl restart traffic-monitor
```

---

## Support

**Need help?**

1. Check logs: `sudo journalctl -u traffic-monitor -n 100`
2. Run diagnostics: `python tools/test_hailo.py`
3. Review docs: `docs/HAILO_SETUP.md`
4. Check implementation: `HAILO_IMPLEMENTATION_SUMMARY.md`

**Ready to deploy!** 🚀

Your Pi is configured for 24/7 unattended traffic monitoring with Hailo acceleration.

---

**Last Updated:** January 16, 2026  
**Tested On:** Raspberry Pi 5 (8GB) + AI HAT+ + Camera Module 3
