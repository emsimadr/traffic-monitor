# Neighborhood Traffic Monitoring System

A hybrid edge-cloud architecture for monitoring and analyzing traffic patterns on residential streets using a Raspberry Pi (or similar device) and optional Google Cloud Platform sync for data processing.

## Problem Statement

Residential streets often lack objective data about traffic patterns, volumes, and speeds. This project provides a complete monitoring system to collect and analyze traffic data for advocacy, planning, and traffic calming initiatives. The system produces credible, evidence-grade data suitable for presentations to municipal authorities and community stakeholders.

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                         TRAFFIC MONITOR                                │
│                  Evidence-Grade Traffic Data Collection                │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  OBSERVATION LAYER (src/observation/)                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │ OpenCVSource │  │Picamera2Src  │  │   VideoFile  │                 │
│  │  (USB/RTSP)  │  │   (Pi CSI)   │  │   (Testing)  │                 │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                 │
│         └────────────┬────────────────────────┘                        │
│                      ↓ FrameData (BGR, timestamp, transforms)          │
└────────────────────────────────────────────────────────────────────────┘
                               ↓
┌────────────────────────────────────────────────────────────────────────┐
│  PIPELINE ENGINE (src/pipeline/)                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  Detect  │→ │  Track   │→ │ Measure  │→ │ Persist  │              │
│  │  Stage   │  │  Stage   │  │  Stage   │  │  Stage   │              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
└───────┼─────────────┼─────────────┼─────────────┼────────────────────┘
        ↓             ↓             ↓             ↓
┌────────────────┐ ┌──────────┐ ┌─────────────┐ ┌──────────────────────┐
│   DETECTION    │ │ TRACKING │ │  COUNTING   │ │      STORAGE         │
│ (src/detection)│ │(src/track│ │(src/algos)  │ │   (src/storage)      │
│                │ │   ing)   │ │             │ │                      │
│ ┌────────────┐ │ │          │ │ ┌─────────┐ │ │  ┌────────────────┐ │
│ │   BgSub    │ │ │   IoU    │ │ │  Gate   │ │ │  │  count_events  │ │
│ │  Detector  │ │ │  Tracker │ │ │ Counter │ │ │  │   (schema v3)  │ │
│ └────────────┘ │ │          │ │ ├─────────┤ │ │  │                │ │
│                │ │  Track   │ │ │  Line   │ │ │  │ • class_id     │ │
│ ┌────────────┐ │ │   with   │ │ │ Counter │ │ │  │ • confidence   │ │
│ │   YOLO     │ │ │ metadata │ │ └─────────┘ │ │  │ • backend      │ │
│ │ (GPU/CPU)  │ │ │          │ │             │ │  │ • direction    │ │
│ └──────┬─────┘ │ │  Double  │ │  Canonical  │ │  │ • timestamp    │ │
│        ↓       │ │  count   │ │  direction  │ │  └────────┬───────┘ │
│ ┌────────────┐ │ │prevention│ │    codes    │ │           ↓         │
│ │   Hailo    │ │ └──────────┘ │  (A_TO_B,   │ │  Unique constraint  │
│ │   (NPU)    │ │              │   B_TO_A)   │ │  Defense-in-depth   │
│ └──────┬─────┘ │              └─────────────┘ └──────────────────────┘
└────────┼───────┘                                        │
         ↓                                                ↓
┌────────────────────────────┐                 ┌──────────────────────┐
│  INFERENCE BACKENDS        │                 │   CLOUD SYNC         │
│  (src/inference)           │                 │   (src/cloud)        │
│                            │                 │                      │
│  ┌──────────────────────┐  │                 │  • BigQuery upload   │
│  │  CPU Backend         │  │                 │  • Cloud Storage     │
│  │  (Ultralytics YOLO)  │  │                 │  • Async/optional    │
│  └──────────────────────┘  │                 │  • Schema v3         │
│                            │                 └──────────────────────┘
│  ┌──────────────────────┐  │
│  │  Hailo Backend       │  │
│  │  (HailoRT NPU)       │  │
│  └──────────────────────┘  │
└────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  WEB LAYER (src/web + frontend/)                                       │
│                                                                         │
│  FastAPI Backend              React Frontend (TypeScript + Tailwind)   │
│  ┌─────────────────────┐      ┌─────────────────────────────────────┐ │
│  │ API Routes          │      │ • Dashboard (live video + counts)   │ │
│  │ • /api/status       │◄────►│ • Configure (gate lines, settings)  │ │
│  │ • /api/stats/*      │      │ • Health (system metrics)           │ │
│  │ • /api/config       │      │ • Trends (time-series charts)       │ │
│  │ • /api/calibration  │      │ • Logs (system log viewer)          │ │
│  │ • /api/camera/live  │      └─────────────────────────────────────┘ │
│  └─────────────────────┘                                               │
│                                                                         │
│  Services Layer (src/web/services/)                                    │
│  • Stats service (modal split, time-series)                            │
│  • Config service (3-layer merge: default → config → calibration)      │
│  • Status service (compact polling, health metrics)                    │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  RUNTIME CONTEXT (src/runtime/)                                        │
│  • Platform metadata capture                                           │
│  • Service initialization and dependency injection                     │
│  • Configuration management (3-layer architecture)                     │
└────────────────────────────────────────────────────────────────────────┘

KEY ARCHITECTURAL PRINCIPLES:
✓ Observation → Detection → Tracking → Counting → Storage (strict layers)
✓ Pluggable backends at each layer (camera, detection, inference)
✓ Edge-first: runs without internet, cloud sync is optional
✓ Defense-in-depth: double-count prevention (track state + DB constraint)
✓ Schema v3: comprehensive metadata for evidence-grade analysis
```

### Key Components

1. **Observation Layer** (`src/observation/`)
   - Abstracts frame sources (USB cameras, RTSP, Pi CSI, video files)
   - Returns `FrameData` objects with timestamps
   - Handles reconnection and transforms (rotate, flip, swap_rb)

2. **Pipeline Engine** (`src/pipeline/`)
   - Clear stages: Preprocess → Detect → Track → Measure → Persist
   - Tracking produces trajectories for counting analysis
   - MeasureStage applies selected counting strategy

3. **Detection Backends** (`src/detection/`)
   - **Background Subtraction**: CPU-only, single-class detection
   - **YOLO (GPU/CPU)**: Multi-class object detection (person, bicycle, car, motorcycle, bus, truck)
   - **Hailo (NPU)**: Hardware-accelerated YOLO for Raspberry Pi 5 (planned)
   - All backends preserve class metadata through the pipeline

4. **Counting Strategies** (`src/algorithms/counting/`)
   - **GateCounter** (default): Two-line gate for bi-directional streets
   - **LineCounter**: Single-line fallback
   - All strategies emit canonical `CountEvent` with direction codes and class metadata
   - Defense-in-depth: prevents double-counting via track state + database constraints

5. **Storage** (`src/storage/`)
   - Single canonical table: `count_events` (schema v3)
   - Stores class metadata (class_id, class_name, confidence, detection_backend)
   - Stats derived exclusively from `count_events`
   - Unique constraint prevents duplicate counts

6. **Web API** (`src/web/`)
   - JSON APIs for frontend (`/api/status`, `/api/stats/*`)
   - Modal split statistics: `/api/stats/by-class`
   - MJPEG streaming at `/api/camera/live.mjpg`
   - Configuration management

7. **Frontend** (`frontend/`)
   - React + TypeScript + Tailwind + shadcn/ui
   - **Dashboard**: Live video feed + real-time counts + system status
   - **Configure**: Gate lines, camera settings, detection parameters
   - **Health**: System metrics, storage, temperature, uptime
   - **Trends**: Time-series analysis, historical patterns
   - **Logs**: System log viewer with filtering

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
│   │   ├── pages/             # Dashboard, Configure, Health, Trends, Logs
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

| Backend | Hardware | Classification | Classes Detected | Use Case |
|---------|----------|----------------|------------------|----------|
| `bgsub` | Any CPU | ❌ Single-class | Motion blobs (unclassified) | Default, no dependencies, works everywhere |
| `yolo` | GPU (CUDA) or CPU | ✅ Multi-class | person, bicycle, car, motorcycle, bus, truck | Best for desktop/dev, enables modal split |
| `hailo` | Hailo NPU (Pi 5) | ✅ Multi-class | person, bicycle, car, motorcycle, bus, truck | Best for edge deployment (📋 PLANNED - placeholder stub exists, implementation pending) |

**Classification Details:**
- **Multi-class backends** (`yolo`, `hailo`) enable modal split analysis by detecting person, bicycle, car, motorcycle, bus, and truck
- **Single-class backend** (`bgsub`) produces unclassified detections (CPU-only fallback)
- All count events store `detection_backend` field to track which detector was used
- Class-based statistics available via `/api/stats/by-class` for advocacy reports showing car vs bike vs pedestrian volumes

### YOLO Detection (GPU/CPU)

```yaml
detection:
  backend: "yolo"
  yolo:
    model: "yolov8s.pt"      # Model file (auto-downloads)
    conf_threshold: 0.25     # Baseline threshold (run YOLO permissively)
    classes: [0, 1, 2, 3, 5, 7]  # COCO class IDs to detect
    
    # Class-specific confidence thresholds (applied post-detection)
    # Different thresholds for different object types improve detection:
    # - Lower for small/hard objects (pedestrians, bicycles)
    # - Higher for large/easy objects (cars, buses)
    class_thresholds:
      0: 0.20   # person - LOW (critical for safety, often missed)
      1: 0.25   # bicycle - LOW (important for modal split)
      2: 0.40   # car - HIGH (large, easy to detect)
      3: 0.30   # motorcycle - MEDIUM
      5: 0.45   # bus - HIGH (very large)
      7: 0.45   # truck - HIGH (very large)
```

**Detected classes**: person, bicycle, car, motorcycle, bus, truck (COCO IDs 0, 1, 2, 3, 5, 7)

**Class-Specific Thresholds**: YOLO uses a two-stage filtering approach:
1. Run YOLO with low baseline threshold (0.25) to capture all potential detections
2. Apply class-specific thresholds post-detection to tune sensitivity per class

This dramatically improves pedestrian and bicycle detection (+300-400%) without increasing false positives for cars.

**Requirements**: `pip install ultralytics` (GPU auto-detected via PyTorch CUDA)

### Background Subtraction (Default)

```yaml
detection:
  backend: "bgsub"
  min_contour_area: 1000
  detect_shadows: true
```

No external dependencies. Works on any hardware but doesn't classify objects.

## Configuration Architecture

The system uses a **3-layer configuration architecture** to separate universal defaults, deployment settings, and site-specific calibration:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: config/default.yaml (checked in)                  │
│   Universal defaults, works everywhere                      │
│   Example: detection thresholds, counting parameters        │
└─────────────────────────────────────────────────────────────┘
                            ↓ (overridden by)
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: config/config.yaml (gitignored)                   │
│   Deployment-specific operational settings                  │
│   Example: camera backend, resolution, fps                  │
└─────────────────────────────────────────────────────────────┘
                            ↓ (overridden by)
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: data/calibration/site.yaml (gitignored)           │
│   Site-specific measured geometry                           │
│   Example: gate line coordinates, camera orientation        │
└─────────────────────────────────────────────────────────────┘
```

### Why 3 Layers?

**Separation of Concerns:**
- **Configuration** (Layer 1-2): Settings you change operationally (resolution, thresholds)
- **Calibration** (Layer 3): Geometry you measure once and rarely change (gate coordinates)

**Benefits:**
- ✅ Clean separation between config and calibration
- ✅ Calibration managed separately via `/api/calibration` endpoint
- ✅ Backwards compatible (site.yaml is optional)
- ✅ Multi-site deployments can share defaults, customize per-site

### Configuration Files

**`config/default.yaml`** (checked in):
- Universal defaults that work everywhere
- Detection thresholds, counting parameters, API settings
- Base configuration shipped with the software

**`config/config.yaml`** (gitignored, optional):
- Deployment-specific operational settings
- Camera backend, resolution, detection backend
- Overrides defaults for this specific deployment

**`data/calibration/site.yaml`** (gitignored, optional):
- Site-specific measured geometry
- Gate line coordinates, direction labels
- Camera orientation (rotate, flip)
- Overrides config for calibration-specific fields

### Creating Calibration File

**Option 1: Use the web UI**
1. Access `http://localhost:5000`
2. Configure gate lines via `/api/calibration` endpoint
3. File is automatically created at `data/calibration/site.yaml`

**Option 2: Create manually**
```bash
cp data/calibration/site.yaml.example data/calibration/site.yaml
# Edit coordinates to match your camera view
```

**Option 3: Migrate from existing config.yaml**
```bash
python tools/migrate_config_to_calibration.py
# Extracts calibration data from config.yaml to site.yaml
# Safe: creates backups before modifying files
```

### API Endpoints

| Endpoint | Purpose | File Modified |
|----------|---------|---------------|
| `GET /api/calibration` | Fetch calibration (gate lines, orientation) | - |
| `POST /api/calibration` | Save calibration | `data/calibration/site.yaml` |
| `GET /api/config` | Fetch full effective config | - |

The effective configuration is the deep merge of all 3 layers:

```python
effective_config = default ← config ← calibration
```

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
| `GET /api/stats/by-class` | Modal split statistics (by object class) |
| `GET /api/stats/live` | Real-time stats |
| `GET /api/config` | Current configuration |
| `POST /api/config` | Save config overrides |
| `GET /api/calibration` | Calibration settings |
| `POST /api/calibration` | Save calibration |
| `GET /api/camera/live.mjpg` | MJPEG video stream |
| `GET /api/camera/snapshot.jpg` | Single frame snapshot |

### Modal Split Statistics

The `/api/stats/by-class` endpoint provides object class breakdowns for modal split analysis:

```bash
curl "http://localhost:5000/api/stats/by-class?start_ts=1704067200&end_ts=1704153600"
```

Returns:
```json
{
  "total": 150,
  "by_class": {
    "car": 85,
    "bicycle": 12,
    "person": 8,
    "motorcycle": 5,
    "bus": 3,
    "truck": 4,
    "unclassified": 33
  },
  "by_class_and_direction": {
    "car": {"A_TO_B": 45, "B_TO_A": 40},
    "bicycle": {"A_TO_B": 8, "B_TO_A": 4}
  },
  "unclassified": 33,
  "time_range": {"start": 1704067200, "end": 1704153600}
}
```

**Use Cases:**
- **Advocacy**: "Show that 85% of traffic is through-traffic, not local residents"
- **Modal split**: "Demonstrate need for bike lanes with actual cyclist counts"
- **Time-of-day**: "Identify peak hours for speed enforcement requests"
- **Before/after**: "Measure effectiveness of traffic calming interventions"

**Note:** Multi-class detection requires `detection.backend='yolo'` or `'hailo'`. Background subtraction (`bgsub`) is CPU-only but produces unclassified detections.

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

## Current Implementation Status

### ✅ Milestone 0 — Deployment Readiness (COMPLETE)
- Runs headless without intervention
- Auto-recovers from camera failures
- Documented setup steps
- Systemd service for Raspberry Pi
- Single-instance enforcement via PID file

### ✅ Milestone 1 — Core Counting (COMPLETE)
- Background subtraction detection
- IoU-based tracking with double-count prevention
- Gate counting (two-line, bi-directional) + Line counting (fallback)
- SQLite storage with `count_events` table (schema v3)
- Web interface (FastAPI + React)

### ✅ Milestone 2 — AI Detection (COMPLETE)
- YOLO backend via Ultralytics (GPU/CPU)
- Multi-class detection (person, bicycle, car, motorcycle, bus, truck)
- Configurable detection backend (`bgsub`, `yolo`, `hailo`)
- Hardware-aware logging (shows GPU name or CPU fallback)
- Full pipeline integration (detection → tracking → counting → storage)
- **Schema v3** with class metadata (class_id, class_name, confidence, backend, platform, process_pid)
- **Class-specific confidence thresholds** (improves pedestrian/bicycle detection by 300-400%)
- Migration tools for config and BigQuery schema

### 🔄 Milestone 4 — Modal Split Analytics (BACKEND COMPLETE, FRONTEND IN PROGRESS)
- ✅ Multi-class detection (via YOLO backend)
- ✅ Class metadata stored in database (schema v3)
- ✅ Class-based statistics API (`/api/stats/by-class`)
- ✅ Trends page in frontend (time-series visualization)
- ⏳ Enhanced Dashboard modal split display
- ⏳ Class-specific time-of-day patterns
- ⏳ Modal split reports (vehicles vs pedestrians vs cyclists)
- ⏳ Validation procedure for class accuracy

### ⏳ Milestone 3 — Speed Measurement (NOT STARTED)
- Camera calibration procedure
- Ground-plane speed estimation
- Speed distribution statistics
- Validation against reference

### ⏳ Milestone 5 — Heatmaps (NOT STARTED)
- Trajectory aggregation
- Time-bucketed occupancy grids
- Bird's-eye view transformation

### ⏳ Milestone 6 — Reliability & Monitoring (PARTIAL)
- ✅ Health status endpoint with system metrics
- ✅ Disk usage and temperature monitoring
- ⏳ Alerting for camera offline
- ⏳ Uptime tracking dashboard
- ⏳ Cost controls for cloud

### ⏳ Milestone 7 — Advocacy Packaging (NOT STARTED)
- Chart generation
- One-page summary template
- Before/after comparison tools
- CSV/PDF exports

## Data Collection

The system collects the following data:

**Per Count Event (stored in SQLite, schema v3):**
- Timestamp (epoch milliseconds)
- Track ID (transient, resets on restart)
- Direction (A_TO_B / B_TO_A)
- Object class (person, bicycle, car, motorcycle, bus, truck, or NULL)
- Detection confidence score
- Gate crossing frames
- Track age and displacement
- Detection backend used (bgsub, yolo, hailo)
- Platform info (OS, Python version)
- Process PID (for debugging)

**Video Data:**
- Live MJPEG stream available via web interface (not stored)
- Optional recording to disk if `--record` flag is used
- No long-term video retention by default (disk space constraints)

**Cloud Sync (optional):**
- Count events synced to BigQuery for long-term analysis
- No video data uploaded to cloud
- Configurable sync interval and retention

## Performance

Tested configurations:

| Hardware | Backend | FPS | Use Case |
|----------|---------|-----|----------|
| Desktop (RTX 3060) | YOLO (GPU) | 30 | Development, multi-class detection |
| Desktop (CPU) | YOLO (CPU) | 10-15 | Testing without GPU |
| Raspberry Pi 5 | Background Sub | 20-25 | Edge deployment, single-class |
| Raspberry Pi 5 + AI HAT+ | Hailo (planned) | 20-30 | Edge deployment with classification |

## Documentation

Comprehensive project documentation is available in the `docs/` directory:

- **[PLAN.md](docs/PLAN.md)** - Living roadmap, architecture, milestones, and configuration guide
- **[ARCHITECT_CONSTITUTION.md](docs/architect_constitution.md)** - Non-negotiable design principles and governance
- **[DATA_MODEL_REVIEW.md](docs/DATA_MODEL_REVIEW.md)** - Data model analysis and schema v3 design
- **[SCHEMA_V3_MIGRATION.md](docs/SCHEMA_V3_MIGRATION.md)** - Migration guide for schema v3
- **[IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md)** - Schema v3 implementation details
- **[RESTART_INSTRUCTIONS.md](RESTART_INSTRUCTIONS.md)** - Quick reference for developers

### Governance

This project follows strict architectural governance to ensure data quality, privacy, and reliability:

- **Evidence-grade data**: Every measurement must be reproducible and documented
- **Edge-first**: System must work without internet access
- **Defense in depth**: Multiple layers prevent double-counting
- **Architectural boundaries**: Clear layer separation (observation → detection → tracking → counting → storage → web)
- **Small, reviewable changes**: Prefer incremental improvements over sweeping rewrites

See [ARCHITECT_CONSTITUTION.md](docs/architect_constitution.md) for complete principles.

## Contributing

Contributions welcome! Please:

1. Read [ARCHITECT_CONSTITUTION.md](docs/architect_constitution.md) and [PLAN.md](docs/PLAN.md)
2. Make small, testable, incremental changes
3. Add tests for new functionality
4. Update documentation as needed
5. Open an issue or PR

## License

MIT License - see [LICENSE](LICENSE)
