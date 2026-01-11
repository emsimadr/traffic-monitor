# Neighborhood Traffic Monitoring System

A hybrid edge-cloud architecture for monitoring and analyzing traffic patterns on residential streets using a Raspberry Pi (or similar device) and optional Google Cloud Platform sync for data processing.

## Problem Statement

Our residential street has become increasingly dangerous due to high traffic volumes and reckless driving. This project systematically collects and analyzes traffic data to build an evidence-based case for implementing traffic calming measures.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        TRAFFIC MONITOR                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │ Observation │ -> │  Pipeline   │ -> │   Storage   │          │
│  │   Layer     │    │   Engine    │    │   (SQLite)  │          │
│  └─────────────┘    └─────────────┘    └─────────────┘          │
│        │                  │                   │                  │
│        │                  │                   │                  │
│  ┌─────┴─────┐     ┌─────┴─────┐      ┌─────┴─────┐             │
│  │ OpenCV    │     │ Detect    │      │  Cloud    │             │
│  │ Picamera2 │     │ Track     │      │  Sync     │             │
│  └───────────┘     │ Measure   │      │ (BigQuery)│             │
│                    └───────────┘      └───────────┘             │
│                          │                                       │
│                    ┌─────┴─────┐                                 │
│                    │ Counting  │                                 │
│                    │ Strategies│                                 │
│                    │ (Gate/    │                                 │
│                    │  Line)    │                                 │
│                    └───────────┘                                 │
│                                                                   │
├──────────────────────────────────────────────────────────────────┤
│  Web Interface (React + FastAPI)                                 │
│  - Dashboard: Live video + counts + alerts                       │
│  - Configure: Gate lines, camera settings, detection params      │
│  - Health: System stats, storage, temperature                    │
└──────────────────────────────────────────────────────────────────┘
```

### Key Components

1. **Observation Layer** (`src/observation/`)
   - Abstracts frame sources (USB cameras, RTSP, Pi CSI, video files)
   - Returns `FrameData` objects with timestamps
   - Handles reconnection and transforms (rotate, flip, swap_rb)

2. **Pipeline Engine** (`src/pipeline/`)
   - Clear stages: Preprocess → Detect → Track → Measure → Persist
   - Tracking produces trajectories only (no counting side effects)
   - MeasureStage applies selected counting strategy

3. **Counting Strategies** (`src/algorithms/counting/`)
   - **GateCounter** (default): Two-line gate for bi-directional streets
   - **LineCounter**: Single-line fallback
   - All strategies emit canonical `CountEvent` with `A_TO_B`/`B_TO_A` direction codes
   - Syncs `has_been_counted` to tracks to prevent double-counting from track fragmentation

4. **Storage** (`src/storage/`)
   - Single canonical table: `count_events`
   - Stats derived exclusively from `count_events`
   - Schema versioning via `schema_meta` table (current: v2)
   - Unique constraint prevents duplicate counts (defense-in-depth)

5. **Web API** (`src/web/`)
   - JSON APIs for frontend
   - `/api/status` primary polling endpoint
   - MJPEG streaming at `/api/camera/live.mjpg`

6. **Frontend** (`frontend/`)
   - React + TypeScript + Tailwind + shadcn/ui
   - Dashboard, Configuration, Health pages

## Project Structure

```
traffic-monitor/
├── config/                     # Configuration
│   ├── default.yaml           # Defaults (do not edit)
│   ├── config.yaml            # Local overrides
│   └── cloud_config.yaml      # GCP settings
│
├── src/                        # Backend source
│   ├── main.py                # Entry point
│   ├── observation/           # Frame sources (OpenCV, Picamera2)
│   ├── pipeline/              # Processing engine + stages
│   ├── algorithms/counting/   # Counting strategies (Gate, Line)
│   ├── detection/             # Detection (BgSub detector)
│   ├── inference/             # AI backends (YOLO/GPU, Hailo/NPU)
│   ├── tracking/              # Object tracking
│   ├── storage/               # SQLite database
│   ├── models/                # Data models (FrameData, CountEvent, etc.)
│   ├── runtime/               # Runtime context + services
│   ├── web/                   # FastAPI + Jinja2 (legacy)
│   │   ├── routes/            # API routes
│   │   └── services/          # Business logic
│   ├── cloud/                 # GCP sync
│   └── ops/                   # Logging, health, process management
│
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── pages/             # Dashboard, Configure, Health
│   │   ├── components/        # UI components
│   │   └── lib/               # API client, utilities
│   └── dist/                  # Built frontend (served by FastAPI)
│
├── secrets/                    # Credentials (gitignored)
│   ├── gcp-credentials.json
│   └── camera_secrets.yaml
│
├── tests/                      # Unit tests
├── docs/                       # Documentation
└── tools/                      # Deployment scripts
```

## Quick Start

### 1. Install Dependencies

```bash
git clone https://github.com/your-username/traffic-monitor.git
cd traffic-monitor

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install Python dependencies
pip install -r requirements.txt

# Build frontend
cd frontend
npm install
npm run build
cd ..
```

### 2. Configure

Copy and edit the config:

```bash
cp config/default.yaml config/config.yaml
```

**For USB camera:**
```yaml
camera:
  backend: "opencv"
  device_id: 0
  resolution: [1280, 720]
  fps: 30

counting:
  mode: "gate"  # Two-line gate counting (default)
  line_a: [[0.2, 1.0], [0.0, 0.0]]
  line_b: [[0.8, 1.0], [1.0, 0.0]]
  direction_labels:
    a_to_b: "northbound"
    b_to_a: "southbound"
```

**For Pi Camera:**
```yaml
camera:
  backend: "picamera2"
  resolution: [1280, 720]
  fps: 30
```

**For RTSP camera:**
```yaml
camera:
  backend: "opencv"
  device_id: "rtsp://192.168.1.100/stream"
  secrets_file: "secrets/camera_secrets.yaml"
```

### 3. Run

```bash
python src/main.py --config config/config.yaml
```

Access the web interface at: `http://localhost:5000`

### Options

- `--display`: Show OpenCV window (for debugging)
- `--record`: Record video to `output/video/`
- `--stop`: Stop any running instance and exit
- `--kill-existing`: Kill existing instance before starting (ensures single instance)

### Process Management

The system enforces single-instance operation via PID file (`data/traffic_monitor.pid`):

```bash
# Stop a running instance
python src/main.py --stop

# Replace existing instance
python src/main.py --config config/config.yaml --kill-existing
```

## Counting Strategies

### Gate Counting (Default)

Two-line gate counting is the standard for bi-directional streets:

```
        Line A          Line B
          │               │
    ──────┼───────────────┼──────
          │    STREET     │
    ──────┼───────────────┼──────
          │               │

Vehicle crossing A → B = "A_TO_B" (northbound)
Vehicle crossing B → A = "B_TO_A" (southbound)
```

Configure in `config.yaml`:
```yaml
counting:
  mode: "gate"
  line_a: [[0.2, 1.0], [0.0, 0.0]]  # Ratios [0-1]
  line_b: [[0.8, 1.0], [1.0, 0.0]]
  max_gap_frames: 30  # Max frames between A/B crossings
```

### Line Counting (Fallback)

Single-line counting for simple scenarios:

```yaml
counting:
  mode: "line"
  line_a: [[0.5, 1.0], [0.5, 0.0]]  # Vertical center line
```

## Detection Backends

The system supports multiple detection backends, configurable for different hardware:

| Backend | Hardware | Use Case |
|---------|----------|----------|
| `bgsub` | Any CPU | Default, no dependencies, works everywhere |
| `yolo` | GPU (CUDA) or CPU | YOLO via Ultralytics, best for desktop/dev |
| `hailo` | Hailo NPU (Pi 5) | YOLO on AI HAT+, best for edge deployment |

### YOLO Detection (GPU/CPU)

```yaml
detection:
  backend: "yolo"
  yolo:
    model: "yolov8s.pt"      # Model file (auto-downloads)
    conf_threshold: 0.35     # Confidence threshold
    classes: [0, 1, 2, 3, 5, 7]  # COCO class IDs to detect
    class_name_overrides:
      0: "person"
      1: "bicycle"
      2: "car"
      3: "motorcycle"
      5: "bus"
      7: "truck"
```

**Detected classes**: person, bicycle, car, motorcycle, bus, truck (COCO IDs 0, 1, 2, 3, 5, 7)

**Requirements**: `pip install ultralytics` (GPU auto-detected via PyTorch CUDA)

### Background Subtraction (Default)

```yaml
detection:
  backend: "bgsub"
  min_contour_area: 1000
  detect_shadows: true
```

No external dependencies. Works on any hardware but doesn't classify objects.

## Raspberry Pi Deployment

### Automated Setup

```bash
ssh pi@traffic-pi.local
git clone https://github.com/your-username/traffic-monitor.git
cd traffic-monitor
chmod +x tools/deploy_pi.sh
sudo ./tools/deploy_pi.sh
```

### Manual Setup

```bash
# Install system packages
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip \
  python3-opencv python3-picamera2 rpicam-apps nodejs npm

# Create venv (include system packages for picamera2)
python3 -m venv --system-site-packages .venv
source .venv/bin/activate

# Install Python deps (skip opencv-python on Pi)
grep -v '^opencv-python' requirements.txt > /tmp/req.txt
pip install -r /tmp/req.txt

# Build frontend
cd frontend && npm install && npm run build && cd ..

# Create systemd service
sudo nano /etc/systemd/system/traffic-monitor.service
```

Systemd service file:
```ini
[Unit]
Description=Traffic Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/traffic-monitor
Environment="PATH=/home/pi/traffic-monitor/.venv/bin:/usr/bin"
ExecStart=/home/pi/traffic-monitor/.venv/bin/python src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable traffic-monitor
sudo systemctl start traffic-monitor
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/status` | Compact status for dashboard polling |
| `GET /api/health` | System health info |
| `GET /api/stats/summary` | Count statistics |
| `GET /api/stats/live` | Real-time stats |
| `GET /api/config` | Current configuration |
| `POST /api/config` | Save config overrides |
| `GET /api/calibration` | Calibration settings |
| `POST /api/calibration` | Save calibration |
| `GET /api/camera/live.mjpg` | MJPEG video stream |
| `GET /api/camera/snapshot.jpg` | Single frame snapshot |

## Cloud Sync (Optional)

To sync data to Google Cloud BigQuery:

1. Create a GCP project
2. Enable BigQuery API
3. Create a service account with `BigQuery Data Editor` role
4. Download key to `secrets/gcp-credentials.json`
5. Configure `config/cloud_config.yaml`

## Development

```bash
# Run tests
pytest tests/ -v

# Build frontend in dev mode
cd frontend && npm run dev

# Run backend
python src/main.py --display
```

## Contributing

Contributions welcome! Please open an issue or PR.

## License

MIT License - see [LICENSE](LICENSE)
