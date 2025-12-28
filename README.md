# Neighborhood Traffic Monitoring System

A hybrid edge-cloud architecture for monitoring and analyzing traffic patterns on residential streets using a Raspberry Pi (or similar device) and Google Cloud Platform for data processing.

## Problem Statement

Our residential street has become increasingly dangerous due to high traffic volumes and reckless driving, creating an unsafe environment for residents, pedestrians, and especially children. Despite frequent close calls and community concerns, we lack the quantitative data necessary to compel municipal action for traffic calming measures.

This project systematically collects and analyzes traffic data to build an evidence-based case for implementing traffic calming measures such as speed bumps, enhanced signage, and integrated road design that prioritizes safety for all road users.

## Project Architecture

The system uses a hybrid edge-cloud architecture:

### Edge Component (Raspberry Pi / Jetson / PC)
- **Flexible Camera Support**: Works with USB Webcams, Raspberry Pi Cameras (libcamera), and IP Cameras (RTSP/HTTP).
- **Intelligent Detection**: Supports both traditional Computer Vision (Background Subtraction) and AI-powered detection (YOLOv8).
- **Vehicle Tracking**: Tracks vehicles across frames to count unique vehicles and determine direction.
- **Robust Storage**: Temporarily stores data locally in SQLite with automatic cleanup.
- **Resilient Cloud Sync**: Syncs data to Google Cloud BigQuery and Cloud Storage with retry logic.

### Cloud Component (Google Cloud Platform)
- **BigQuery**: Stores the complete dataset for long-term analysis.
- **Cloud Storage**: Archives video samples of traffic events.
- **Looker Studio**: Visualizes traffic patterns, peak hours, and speeding trends.

![System Architecture](docs/images/architecture-diagram.png)

## Key Features

*   **Vehicle Counting**: Accurately counts vehicles moving in both directions.
*   **Direction Detection**: Distinguishes between Northbound and Southbound traffic (customizable).
*   **Diagonal Street Support**: Configurable counting lines for any road layout.
*   **RTSP/IP Camera Support**: Connect to wireless security cameras.
*   **AI Ready**: Modular backend supports upgrading to YOLO models for higher accuracy.
*   **Privacy First**: Focuses on counting and statistics, not surveillance.

## Project Structure

```
traffic_monitor/
│
├── config/                      # Configuration files
│   ├── default.yaml             # Default settings (do not edit)
│   ├── config.yaml              # Local overrides (your custom settings)
│   └── cloud_config.yaml        # Cloud-specific configuration
│
├── src/                         # Source code
│   ├── main.py                  # Main application entry point
│   ├── camera/                  # Camera abstraction layer
│   ├── capture/                 # Video capture backends (OpenCV, Picamera2)
│   ├── detection/               # Detection modules (BgSub, YOLO)
│   ├── tracking/                # Object tracking logic
│   ├── analytics/               # Counting and speed estimation
│   ├── storage/                 # Local database handling
│   ├── cloud/                   # GCP synchronization
│   └── ops/                     # Operations (logging, health)
│
├── secrets/                     # Credentials (gitignored)
│   ├── gcp-credentials.json     # GCP service account key
│   └── camera_secrets.yaml      # IP camera credentials
│
├── docs/                        # Documentation
└── tools/                       # Utility scripts
```

## Installation

### 1. Prerequisites
- Python 3.8+
- OpenCV
- (Optional) Raspberry Pi with Camera Module 3 or AI HAT+

### 2. Clone and Install
```bash
git clone https://github.com/your-username/traffic-monitor.git
cd traffic-monitor
# Create a virtual environment
python -m venv .venv
# Activate it (Windows)
.venv\Scripts\activate
# Activate it (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Google Cloud Platform Setup
1. Create a GCP project.
2. Enable BigQuery and Cloud Storage APIs.
3. Create a Service Account with `BigQuery Data Editor` and `Storage Object Admin` roles.
4. Download the JSON key file to `secrets/gcp-credentials.json`.

### 4. Configuration
The system uses a layered configuration. `config/default.yaml` contains defaults. You should create/edit `config/config.yaml` to override them.

**Example `config/config.yaml`:**
```yaml
camera:
  # Use an IP Camera
  device_id: "rtsp://192.168.1.100/stream1"
  secrets_file: "secrets/camera_secrets.yaml"
  # Or use a USB Webcam
  # device_id: 0
  
detection:
  # Define a diagonal counting line [[x1, y1], [x2, y2]] (ratios 0.0-1.0)
  counting_line: [[0.0, 0.0], [1.0, 1.0]]
  
  # Switch to YOLO for better accuracy (requires 'ultralytics' package)
  # backend: "yolo"
  # yolo:
  #   model: "yolov8n.pt"
```

## Usage

**Run with visualization (for testing):**
```bash
python src/main.py --config config/config.yaml --display
```

**Run in background (for deployment):**
```bash
python src/main.py --config config/config.yaml
```

**Record video samples:**
```bash
python src/main.py --config config/config.yaml --record
```

## Raspberry Pi Deployment

### Quick Start (Automated)

For a fresh Raspberry Pi OS (Bookworm) installation:

```bash
# SSH into your Pi
ssh traffic@traffic-pi-01.local

# Clone the repo
git clone https://github.com/emsimadr/traffic-monitor.git
cd traffic-monitor

# Run the deployment script
chmod +x tools/deploy_pi.sh
sudo ./tools/deploy_pi.sh
```

This script will:
- Install system dependencies (python3, opencv, picamera2, etc.)
- Create the `traffic` service user
- Set up the app in `/opt/traffic-monitor`
- Create and enable a systemd service

### Manual Setup

If you prefer manual control or already have the repo cloned:

#### 1. Install system dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-venv python3-pip python3-opencv python3-picamera2 rpicam-apps
```

#### 2. Create Python environment
```bash
cd ~/traffic-monitor
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
grep -v '^opencv-python' requirements.txt > /tmp/requirements.pi.txt
pip install -r /tmp/requirements.pi.txt
```

#### 3. Configure for your camera

**For Picamera2 (CSI ribbon camera):**
```yaml
# config/config.yaml
camera:
  backend: "picamera2"
  resolution: [1280, 720]
  fps: 30
```

**For RTSP/IP camera:**
```yaml
# config/config.yaml
camera:
  backend: "opencv"
  secrets_file: "secrets/camera_secrets.yaml"
```

```yaml
# secrets/camera_secrets.yaml
rtsp_url: "rtsp://192.168.1.100/live0"
username: "admin"
password: "yourpassword"
```

#### 4. Create systemd service
```bash
sudo nano /etc/systemd/system/traffic-monitor.service
```

Paste:
```ini
[Unit]
Description=Traffic Monitor Service
After=network.target

[Service]
Type=simple
User=traffic
WorkingDirectory=/home/traffic/traffic-monitor
Environment="PATH=/home/traffic/traffic-monitor/.venv/bin:/usr/bin"
ExecStart=/home/traffic/traffic-monitor/.venv/bin/python src/main.py --config config/config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 5. Enable and start
```bash
sudo systemctl daemon-reload
sudo systemctl enable traffic-monitor
sudo systemctl start traffic-monitor
```

#### 6. Check status
```bash
sudo systemctl status traffic-monitor
sudo journalctl -u traffic-monitor -f
```

### Updating

After the service is set up, use the update script:

```bash
cd ~/traffic-monitor
chmod +x tools/update_pi.sh
./tools/update_pi.sh
```

Or manually:
```bash
sudo systemctl stop traffic-monitor
git pull
source .venv/bin/activate
pip install -r /tmp/requirements.pi.txt
sudo systemctl start traffic-monitor
```

### Accessing the Web UI

Once running, access the dashboard at:
```
http://traffic-pi-01.local:5000/
```

---

## Web UI (Headless)

This project includes a lightweight Web UI (FastAPI + Jinja templates) intended for headless deployments:

- **Dashboard**: counts + health summary + camera snapshot
- **Config**: edit `config/config.yaml` overrides (defaults in `config/default.yaml`)
- **Calibration (v0)**: live snapshot/preview (ROI/line editor planned)
- **Logs**: tail of `logs/traffic_monitor.log`

### Run the Web UI

```bash
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000
```

Then open `http://<pi-ip>:8000/` on your LAN.

### Notes

- The MJPEG endpoint (`/api/camera/stream.mjpg`) opens the camera for the duration of the stream. In a future version, camera access should be coordinated with the detection pipeline.

## Contributing
Contributions are welcome! Please open an issue or submit a Pull Request.

## License
MIT License - see [LICENSE](LICENSE) for details.
