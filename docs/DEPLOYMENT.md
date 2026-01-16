# Deployment Guide

**Target Audience:** System operators deploying the Traffic Monitoring System  
**Last Updated:** January 16, 2026

---

## Table of Contents

1. [Hardware Requirements](#hardware-requirements)
2. [Raspberry Pi Setup](#raspberry-pi-setup)
3. [Configuration](#configuration)
4. [Operation](#operation)
5. [Monitoring](#monitoring)
6. [Troubleshooting](#troubleshooting)
7. [Cloud Sync (Optional)](#cloud-sync-optional)

---

## Hardware Requirements

### Primary Deployment Target

**Recommended Hardware:**
- **Raspberry Pi 5** (8GB RAM recommended, 4GB minimum)
- **Raspberry Pi Camera Module 3** OR **USB webcam**
- **Optional:** AI HAT+ (Hailo-8L) for YOLO acceleration (when available)
- **Active cooling** (fan or heatsink) - essential for continuous operation
- **Stable power supply** (official Pi power supply recommended)
- **High-endurance microSD** (32GB minimum, 64GB+ recommended)
- **Ethernet connection** (recommended over WiFi for stability)

**Alternative Hardware:**
- Raspberry Pi 4 (4GB+ RAM) - works but slower
- Desktop/laptop for development and testing
- Any Linux/Windows machine with Python 3.9+

### Camera Options

| Backend | Hardware | Use Case | Performance |
|---------|----------|----------|-------------|
| `picamera2` | Pi CSI camera (Camera Module 3) | Raspberry Pi deployment | Best for Pi (direct CSI interface) |
| `opencv` | USB webcam | Any platform | Universal compatibility |
| `opencv` | RTSP IP camera | Remote camera | Network-based, flexible placement |
| `opencv` | Video file | Testing/development | Perfect for development |

**Camera Placement:**
- Mount securely at 10-20 ft height
- Angle: 30-45 degrees from horizontal
- Clear view of street (minimize occlusions)
- Protected from weather
- Stable mount (no vibration)

---

## Raspberry Pi Setup

### Automated Setup (Recommended)

```bash
# 1. SSH into your Raspberry Pi
ssh pi@traffic-pi.local

# 2. Clone repository
git clone https://github.com/your-username/traffic-monitor.git
cd traffic-monitor

# 3. Run automated setup script
chmod +x tools/deploy_pi.sh
sudo ./tools/deploy_pi.sh
```

**What the script does:**
- Installs system packages (python3, opencv, picamera2, nodejs)
- Creates virtual environment with system-site-packages
- Installs Python dependencies
- Builds frontend
- Creates systemd service
- Enables service to start on boot

---

### Manual Setup

If you prefer manual installation or automated script fails:

**Step 1: Install System Packages**
```bash
sudo apt update
sudo apt install -y \
  git \
  python3 python3-venv python3-pip \
  python3-opencv python3-picamera2 \
  rpicam-apps \
  nodejs npm
```

**Step 2: Clone Repository**
```bash
cd ~
git clone https://github.com/your-username/traffic-monitor.git
cd traffic-monitor
```

**Step 3: Create Virtual Environment**
```bash
# Include system-site-packages for picamera2
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
```

**Step 4: Install Python Dependencies**
```bash
# Skip opencv-python on Pi (use system package)
grep -v '^opencv-python' requirements.txt > /tmp/req.txt
pip install -r /tmp/req.txt

# Optional: Install YOLO for multi-class detection
# Only if you have sufficient resources (8GB Pi 5 recommended)
pip install ultralytics
```

**Step 5: Build Frontend**
```bash
cd frontend
npm install
npm run build
cd ..
```

**Step 6: Create Systemd Service**
```bash
sudo nano /etc/systemd/system/traffic-monitor.service
```

**Systemd Service File:**
```ini
[Unit]
Description=Traffic Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/traffic-monitor
Environment="PATH=/home/pi/traffic-monitor/.venv/bin:/usr/bin"
ExecStart=/home/pi/traffic-monitor/.venv/bin/python src/main.py --config config/config.yaml
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Step 7: Enable and Start Service**
```bash
sudo systemctl daemon-reload
sudo systemctl enable traffic-monitor
sudo systemctl start traffic-monitor
```

**Step 8: Verify Running**
```bash
sudo systemctl status traffic-monitor
curl http://localhost:5000/api/health
```

---

## Configuration

### 3-Layer Configuration Architecture

The system uses three configuration layers that merge in order:

```
Layer 1: config/default.yaml (universal defaults, checked in)
         ↓ (overridden by)
Layer 2: config/config.yaml (deployment-specific, gitignored)
         ↓ (overridden by)
Layer 3: data/calibration/site.yaml (site-specific geometry, gitignored)
```

### Layer 1: Default Configuration

**File:** `config/default.yaml` (checked into git)  
**Purpose:** Universal defaults that work everywhere  
**Action:** DO NOT EDIT - override in higher layers

**Contains:**
- Detection thresholds
- Counting parameters
- API settings
- Base configuration

### Layer 2: Deployment Configuration

**File:** `config/config.yaml` (gitignored)  
**Purpose:** Deployment-specific operational settings

**Create from default:**
```bash
cp config/default.yaml config/config.yaml
```

**Example for Raspberry Pi with USB camera:**
```yaml
# config/config.yaml
camera:
  backend: "opencv"       # Use OpenCV backend
  device_id: 0           # First USB camera
  resolution: [1280, 720]
  fps: 20                # Reduce FPS for Pi performance

detection:
  backend: "bgsub"       # Use background subtraction (CPU-only)
  min_contour_area: 1500 # Adjust for your camera angle

# Optional: Enable YOLO if you have Pi 5 with 8GB RAM
# detection:
#   backend: "yolo"
#   yolo:
#     model: "yolov8n.pt"  # Smallest model for Pi
```

**Example for Raspberry Pi with Pi Camera:**
```yaml
# config/config.yaml
camera:
  backend: "picamera2"    # Use Pi Camera backend
  resolution: [1280, 720]
  fps: 20
  rotate: 180            # If camera is mounted upside down

detection:
  backend: "bgsub"
  min_contour_area: 1500
```

**Example for RTSP IP Camera:**
```yaml
# config/config.yaml
camera:
  backend: "opencv"
  device_id: "rtsp://192.168.1.100/stream"
  secrets_file: "secrets/camera_secrets.yaml"
  resolution: [1920, 1080]
  fps: 15

# Create secrets/camera_secrets.yaml:
#   rtsp_url: "rtsp://192.168.1.100/stream"
#   username: "admin"
#   password: "yourpassword"
```

### Layer 3: Site Calibration

**File:** `data/calibration/site.yaml` (gitignored)  
**Purpose:** Site-specific measured geometry (gate lines, direction labels)

**Option 1: Use Web UI (Recommended)**
1. Start system: `python src/main.py --config config/config.yaml`
2. Access dashboard: `http://pi-address:5000`
3. Go to Configure page
4. Set gate lines visually
5. Save (automatically creates `site.yaml`)

**Option 2: Create Manually**
```bash
cp data/calibration/site.yaml.example data/calibration/site.yaml
nano data/calibration/site.yaml
```

**Example site.yaml:**
```yaml
# data/calibration/site.yaml
# Site-specific measured geometry

counting:
  # Gate lines (normalized coordinates 0.0-1.0)
  line_a: [[0.2, 1.0], [0.0, 0.0]]  # Left gate line
  line_b: [[0.8, 1.0], [1.0, 0.0]]  # Right gate line
  
  # Human-readable direction labels
  direction_labels:
    a_to_b: "northbound"   # Traffic crossing A→B
    b_to_a: "southbound"   # Traffic crossing B→A

camera:
  rotate: 0                # 0, 90, 180, or 270 degrees
  flip_horizontal: false   # Mirror horizontally
  flip_vertical: false     # Mirror vertically
```

**Gate Line Placement Tips:**
- Lines should be perpendicular to traffic flow
- Space lines 10-20 feet apart
- Avoid areas with frequent occlusions
- Test with live feed before finalizing

---

## Operation

### Starting and Stopping

**Start (systemd):**
```bash
sudo systemctl start traffic-monitor
```

**Stop (systemd):**
```bash
sudo systemctl stop traffic-monitor
```

**Restart:**
```bash
sudo systemctl restart traffic-monitor
```

**Manual start (development):**
```bash
source .venv/bin/activate
python src/main.py --config config/config.yaml
```

**Manual start with display (debugging):**
```bash
python src/main.py --config config/config.yaml --display
```

### Accessing the Web Interface

**Local Access:**
```
http://localhost:5000
```

**Remote Access:**
```
http://pi-address:5000
```

**Pages:**
- **Dashboard** (`/`) - Live video + counts + system status
- **Configure** (`/configure`) - Gate lines, camera settings
- **Health** (`/health`) - System metrics, storage, temperature
- **Trends** (`/trends`) - Historical analysis, charts
- **Logs** (`/logs`) - System log viewer

### Single Instance Enforcement

The system ensures only one instance runs via PID file (`data/traffic_monitor.pid`).

**Stop any running instance:**
```bash
python src/main.py --stop
```

**Kill and replace existing instance:**
```bash
python src/main.py --config config/config.yaml --kill-existing
```

---

## Monitoring

### Systemd Service Status

**Check service status:**
```bash
sudo systemctl status traffic-monitor
```

**View logs:**
```bash
# Recent logs
sudo journalctl -u traffic-monitor -n 50

# Follow logs (real-time)
sudo journalctl -u traffic-monitor -f

# Logs since boot
sudo journalctl -u traffic-monitor -b
```

### Health Endpoints

**System health:**
```bash
curl http://localhost:5000/api/health | jq
```

**Compact status (dashboard polling):**
```bash
curl http://localhost:5000/api/status/compact | jq
```

**Pipeline health:**
```bash
curl http://localhost:5000/api/status/pipeline | jq
```

### Key Metrics to Monitor

**1. Camera Status**
- `last_frame_age_s` should be < 2 seconds
- If > 10 seconds: camera offline

**2. Disk Space**
- `disk_free_pct` should be > 10%
- Clean old logs if low: `rm logs/*.log.old`

**3. Temperature (Raspberry Pi)**
- `cpu_temp_c` should be < 70°C
- If > 80°C: add cooling or reduce workload

**4. Frame Rate**
- `fps_capture` should match configured FPS
- Lower = camera issues or CPU overload

**5. Counts**
- `counts_today_total` should increase during traffic hours
- Flat during traffic = detection/counting issue

### Automated Monitoring (Recommended)

**Option 1: Simple Cron Health Check**
```bash
# Create health check script
cat > ~/check_traffic_monitor.sh << 'EOF'
#!/bin/bash
RESPONSE=$(curl -s http://localhost:5000/api/health)
if [ $? -ne 0 ]; then
    echo "Traffic monitor is down!" | mail -s "Alert: Traffic Monitor Down" you@example.com
fi
EOF

chmod +x ~/check_traffic_monitor.sh

# Add to crontab (check every 5 minutes)
crontab -e
# Add line: */5 * * * * /home/pi/check_traffic_monitor.sh
```

**Option 2: Prometheus + Grafana (Advanced)**
- Export metrics at `/metrics` endpoint (requires implementation)
- Scrape with Prometheus
- Visualize with Grafana dashboards

---

## Troubleshooting

### Camera Issues

**Problem: No frames captured**
```bash
# Check camera connection
ls -la /dev/video*  # USB cameras
vcgencmd get_camera  # Pi cameras

# Test camera directly
python tools/test_camera.py --device-id 0

# Check logs
sudo journalctl -u traffic-monitor | grep camera
```

**Problem: Poor video quality**
- Adjust resolution in `config.yaml`
- Clean camera lens
- Improve lighting
- Reduce FPS to reduce motion blur

**Problem: RTSP stream not connecting**
- Verify RTSP URL: `ffmpeg -i rtsp://... -frames:v 1 test.jpg`
- Check credentials in `secrets/camera_secrets.yaml`
- Ensure network connectivity to camera
- Some cameras require `/live0`, `/h264`, or similar paths

### Performance Issues

**Problem: High CPU usage**
```bash
# Check CPU usage
top -p $(pgrep -f "python src/main.py")

# Solutions:
# 1. Reduce FPS in config.yaml
# 2. Lower resolution
# 3. Use bgsub instead of YOLO
# 4. Add cooling
```

**Problem: Dropped frames**
- Reduce FPS
- Lower resolution
- Close unnecessary programs
- Upgrade to Pi 5 or add active cooling

### Counting Issues

**Problem: No counts being recorded**
```bash
# Check database
sqlite3 data/database.sqlite "SELECT COUNT(*) FROM count_events;"

# Check detection
curl http://localhost:5000/api/status | jq '.detection'

# Check logs
sudo journalctl -u traffic-monitor | grep "count"
```

**Problem: Inaccurate counts**
- Re-calibrate gate lines via web UI
- Adjust detection parameters
- Validate with ground truth (manual count)
- Check for occlusions in camera view

### System Issues

**Problem: Service won't start**
```bash
# Check service status
sudo systemctl status traffic-monitor

# Check detailed logs
sudo journalctl -u traffic-monitor -n 100

# Common causes:
# - Missing config file
# - Permission issues
# - Port 5000 already in use
# - Virtual environment not activated
```

**Problem: Disk full**
```bash
# Check disk usage
df -h

# Clean old logs
rm logs/*.log.old

# Reduce video recording (if enabled)
# Remove old database backups
rm data/*.sqlite.backup.*
```

---

## Cloud Sync (Optional)

### Google Cloud Platform Setup

**Prerequisites:**
- GCP account with billing enabled
- Project created in GCP Console

**Step 1: Enable APIs**
```bash
gcloud services enable bigquery.googleapis.com
gcloud services enable storage.googleapis.com
```

**Step 2: Create Service Account**
```bash
gcloud iam service-accounts create traffic-monitor \
    --display-name="Traffic Monitor"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:traffic-monitor@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:traffic-monitor@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectCreator"
```

**Step 3: Download Credentials**
```bash
gcloud iam service-accounts keys create secrets/gcp-credentials.json \
    --iam-account=traffic-monitor@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

**Step 4: Create BigQuery Dataset**
```bash
bq mk --dataset --location=US YOUR_PROJECT_ID:traffic_data
```

**Step 5: Configure Cloud Sync**
```yaml
# config/cloud_config.yaml
cloud:
  enabled: true
  gcp:
    project_id: "YOUR_PROJECT_ID"
    credentials_path: "secrets/gcp-credentials.json"
    bigquery:
      dataset: "traffic_data"
      table: "count_events"
    storage:
      bucket: "your-traffic-data-bucket"
```

**Step 6: Run Migration**
```bash
python tools/migrate_bigquery_schema_v3.py \
    --project YOUR_PROJECT_ID \
    --dataset traffic_data \
    --table count_events \
    --credentials secrets/gcp-credentials.json
```

**Step 7: Enable Sync in Config**
```yaml
# config/config.yaml
storage:
  cloud_sync_enabled: true
  cloud_sync_interval_s: 300  # Upload every 5 minutes
```

### Monitoring Cloud Costs

**Set Budget Alerts:**
1. Go to GCP Console → Billing → Budgets & alerts
2. Create budget with email alerts
3. Recommended budget: $50/month for continuous monitoring

**Estimated Costs:**
- BigQuery storage: $0.02/GB/month
- BigQuery inserts: $0.05/GB
- Typical usage: <$10/month for single-site deployment

---

## Validation Procedure

### Baseline Validation

**Objective:** Verify counting accuracy meets evidence-grade standards

**Procedure:**
1. **Select 3 validation windows:**
   - Morning (low traffic)
   - Midday (medium traffic)
   - Evening (high traffic)
   
2. **Record ground truth:**
   - Option A: Save 10-minute video clip, manual count
   - Option B: Live observation with tally counter
   
3. **Compare with system counts:**
   ```sql
   SELECT 
       direction_code,
       COUNT(*) as system_count
   FROM count_events
   WHERE ts >= START_TS AND ts <= END_TS
   GROUP BY direction_code;
   ```

4. **Calculate accuracy:**
   - Overall accuracy: (correct_counts / ground_truth) × 100
   - Direction accuracy: (correct_direction / total_counts) × 100

**Targets:**
- Overall accuracy: ≥ 85%
- Direction accuracy: ≥ 90%

**Document Results:**
```
Validation Date: YYYY-MM-DD
Camera Location: [description]
Conditions: [weather, lighting]
System Version: [git commit hash]

Window 1 (Morning):
- Ground truth: 45 vehicles
- System count: 43 vehicles
- Accuracy: 95.6%

Window 2 (Midday):
- Ground truth: 120 vehicles
- System count: 102 vehicles
- Accuracy: 85.0%

... 

Overall Accuracy: 88.2% ✅
Direction Accuracy: 92.1% ✅
```

### Continuous Validation

**Re-validate when:**
- Camera is repositioned
- Configuration parameters change
- Seasonal lighting changes
- New detection backend deployed
- Accuracy concerns arise

---

## Security Considerations

### Network Security

**Firewall (recommended):**
```bash
# Allow SSH and web interface only from local network
sudo ufw allow from 192.168.1.0/24 to any port 22
sudo ufw allow from 192.168.1.0/24 to any port 5000
sudo ufw enable
```

**HTTPS (recommended for public access):**
- Use reverse proxy (nginx) with Let's Encrypt
- Or use Tailscale/Wireguard VPN

### Data Security

**Secrets management:**
- Never commit `secrets/` folder to git
- Use restrictive permissions: `chmod 600 secrets/*`
- Rotate GCP service account keys annually

**Database backup:**
```bash
# Automated daily backup
crontab -e
# Add: 0 2 * * * cp ~/traffic-monitor/data/database.sqlite ~/backups/database-$(date +\%Y\%m\%d).sqlite
```

---

## Performance Tuning

### For Raspberry Pi 4/5

**Conservative (works everywhere):**
```yaml
camera:
  resolution: [1280, 720]
  fps: 15

detection:
  backend: "bgsub"
```

**Balanced (Pi 5, 8GB):**
```yaml
camera:
  resolution: [1280, 720]
  fps: 20

detection:
  backend: "yolo"
  yolo:
    model: "yolov8n.pt"  # Smallest YOLO model
```

**Aggressive (Pi 5 with cooling):**
```yaml
camera:
  resolution: [1920, 1080]
  fps: 25

detection:
  backend: "yolo"
  yolo:
    model: "yolov8s.pt"  # Standard YOLO model
```

### For Desktop/Server

**GPU-accelerated:**
```yaml
camera:
  resolution: [1920, 1080]
  fps: 30

detection:
  backend: "yolo"
  yolo:
    model: "yolov8m.pt"  # Larger model for better accuracy
```

---

## Conclusion

You should now have a running Traffic Monitoring System. Key points:

1. **Monitor system health** via `/api/health` endpoint
2. **Validate counting accuracy** with ground truth
3. **Calibrate gate lines** for your specific camera placement
4. **Adjust performance** based on your hardware
5. **Enable cloud sync** for long-term analysis (optional)

**For help:**
- Check logs: `sudo journalctl -u traffic-monitor -f`
- Review documentation: `docs/`
- Open GitHub issue for bugs/questions

**Enjoy your evidence-grade traffic data! 🚦📊**

---

**Document Version:** 1.0  
**Last Updated:** January 16, 2026
