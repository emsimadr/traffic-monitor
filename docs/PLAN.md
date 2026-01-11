# Neighborhood Traffic Monitoring System — Plan

This `PLAN.md` is the living roadmap for building an **evidence-grade** traffic monitoring system that runs on an edge device (e.g., Raspberry Pi) and optionally syncs results to Google Cloud for analysis and reporting.

---

## Project Overview

### What we're building

- A system that continuously captures a street-facing video stream, detects and tracks traffic participants, and records counts (and later: speed distributions, vulnerable road users, and movement patterns).
- A hybrid architecture:
  - **Edge**: real-time detection + local buffering/storage so data collection continues without internet.
  - **Cloud (optional)**: long-term storage and analytics (BigQuery) + artifacts (Cloud Storage) to support dashboards and advocacy.

### Scope and non-goals

**In scope (near term):**

- Vehicle counting with direction and time-of-day patterns.
- Multi-class detection for modal split analysis (cars, bikes, pedestrians).
- Speed measurement with a documented, repeatable calibration/validation process.
- Aggregated summaries suitable for advocacy and sharing externally.
- Heatmaps that show where traffic actually flows over time.

**Explicit non-goals:**

- Real-time enforcement or automated ticketing.
- Storing continuous raw video long-term (disk space constraints).

### Why it matters

We need **credible quantitative evidence** (counts, patterns, speeds, and modal splits) to support traffic calming advocacy and to withstand scrutiny from municipal stakeholders. The system prioritizes data quality, reliability, and actionable insights over all other concerns.

---

## Current Architecture (Implemented)

### Layer Summary

| Layer | Module | Responsibility |
|-------|--------|----------------|
| **Observation** | `src/observation/` | Frame capture from cameras/files |
| **Pipeline** | `src/pipeline/` | Main loop: Detect → Track → Measure → Persist |
| **Detection** | `src/detection/`, `src/inference/` | Pluggable backends: BgSub, YOLO (GPU/CPU), Hailo (NPU) |
| **Tracking** | `src/tracking/tracker.py` | IoU-based multi-object tracking |
| **Counting** | `src/algorithms/counting/` | Pluggable strategies (Gate, Line) |
| **Storage** | `src/storage/` | SQLite with count_events table |
| **Web** | `src/web/` | FastAPI + React frontend |
| **Cloud** | `src/cloud/` | Optional BigQuery sync |

### Observation Layer

The observation layer (`src/observation/`) abstracts frame sources:

- **OpenCVSource**: USB cameras, RTSP streams, video files
- **Picamera2Source**: Raspberry Pi CSI cameras

Each source implements `open() → read() → close()` and returns `FrameData` with:
- `frame`: numpy array (BGR)
- `timestamp`: capture time
- `frame_index`: sequence number
- `width`, `height`: dimensions

Transforms (rotate, flip, swap_rb) are applied at the observation layer.

### Pipeline Engine

The pipeline engine (`src/pipeline/engine.py`) runs the main loop:

1. **Read**: Get frame from ObservationSource
2. **Detect**: Run detector (BgSub or YOLO)
3. **Track**: Update tracker with detections
4. **Measure**: Apply counting strategy to tracks
5. **Persist**: Save count events to database
6. **Update**: Push annotated frame to web state

### Counting Strategies

Counting strategies (`src/algorithms/counting/`) are pluggable:

**GateCounter (Default)**: Two-line gate for bi-directional streets
- Counts when track crosses Line A then Line B (A_TO_B)
- Or crosses Line B then Line A (B_TO_A)
- Configurable max_gap_frames, min_age_frames, min_displacement_px

**LineCounter (Fallback)**: Single-line counting
- Counts any crossing of the line
- Maps positive/negative crossings to A_TO_B/B_TO_A

All strategies emit `CountEvent` with canonical direction codes.

**Double-Counting Prevention**:
When a count event is emitted, the counter syncs `has_been_counted=True` to the track object. The tracker then:
1. Continues matching detections against counted vehicles (prevents duplicate tracks)
2. Updates bounding boxes but stops accumulating trajectory
3. Eventually removes counted vehicles after `max_frames_since_seen`

This prevents track ID fragmentation from causing duplicate counts when detection noise
causes a brief tracking mismatch. A unique database constraint provides defense-in-depth.

### Storage Schema

Single canonical table `count_events`:

```sql
CREATE TABLE count_events (
    id INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL,           -- epoch milliseconds
    frame_idx INTEGER,
    track_id INTEGER NOT NULL,
    direction_code TEXT NOT NULL,  -- A_TO_B or B_TO_A
    direction_label TEXT,
    gate_sequence TEXT,
    line_a_cross_frame INTEGER,
    line_b_cross_frame INTEGER,
    track_age_frames INTEGER,
    track_displacement_px REAL,
    cloud_synced INTEGER DEFAULT 0
);

-- Defense-in-depth: prevent duplicate counts for same track within same second
CREATE UNIQUE INDEX idx_count_events_track_second ON count_events(track_id, ts / 1000);
```

Schema versioning via `schema_meta` table. Current version: 2.

### Web Interface

**Frontend** (React + TypeScript + Tailwind):
- Dashboard: Live video + counts + alerts
- Configure: Counting mode, gate lines, camera settings
- Health: System stats

**API Endpoints**:
- `GET /api/status`: Compact status for polling
- `GET /api/health`: System health
- `GET /api/config`, `POST /api/config`: Configuration
- `GET /api/calibration`, `POST /api/calibration`: Line calibration
- `GET /api/camera/live.mjpg`: MJPEG stream
- `GET /api/stats/*`: Count statistics

---

## Hardware Target

### Primary deployment

- Raspberry Pi 5 (8GB+)
- Optional: AI HAT+ (Hailo-8) for YOLO acceleration
- Raspberry Pi Camera Module 3 or USB webcam
- Active cooling + stable power supply
- High-endurance microSD

### Camera options

| Backend | Use Case |
|---------|----------|
| `picamera2` | Pi CSI camera (recommended for Pi) |
| `opencv` | USB webcam, RTSP stream, video file |

---

## Configuration

### 3-Layer Architecture (Implemented)

The system uses a **3-layer configuration architecture** to separate universal defaults, deployment settings, and site-specific calibration:

**Layer 1: `config/default.yaml`** (checked in)
- Universal defaults that work everywhere
- Detection thresholds, counting parameters, API settings
- Base configuration shipped with the software
- **Do not edit**: Override in higher layers

**Layer 2: `config/config.yaml`** (gitignored, optional)
- Deployment-specific operational settings
- Camera backend, resolution, detection backend
- Overrides defaults for this specific deployment

**Layer 3: `data/calibration/site.yaml`** (gitignored, optional)
- Site-specific measured geometry
- Gate line coordinates, direction labels
- Camera orientation (rotate, flip)
- Overrides config for calibration-specific fields

**Merge order**: `default ← config ← calibration`

### Rationale

**Separation of Concerns:**
- **Configuration** (Layer 1-2): Settings you change operationally
- **Calibration** (Layer 3): Geometry you measure once and rarely change

**Benefits:**
- ✅ Clean separation between config and calibration
- ✅ Calibration managed separately via `/api/calibration` endpoint
- ✅ Backwards compatible (site.yaml is optional)
- ✅ Multi-site deployments can share defaults, customize per-site
- ✅ Gate coordinates are no longer "configuration" — they're calibration

### Migration

For existing deployments with gate coordinates in `config.yaml`:

```bash
python tools/migrate_config_to_calibration.py
```

This tool:
1. Extracts calibration data from `config.yaml`
2. Creates `data/calibration/site.yaml`
3. Removes calibration data from `config.yaml` (with backup)

### Example: site.yaml

```yaml
# data/calibration/site.yaml
# Site-specific measured geometry

counting:
  line_a: [[0.2, 1.0], [0.0, 0.0]]
  line_b: [[0.8, 1.0], [1.0, 0.0]]
  direction_labels:
    a_to_b: "northbound"
    b_to_a: "southbound"

camera:
  rotate: 0
  flip_horizontal: false
```

### Example: config.yaml

```yaml
# config/config.yaml
# Deployment-specific operational settings

camera:
  backend: "opencv"
  device_id: 0
  resolution: [1280, 720]
  fps: 30

detection:
  backend: "yolo"
  yolo:
    model: "yolov8s.pt"
    conf_threshold: 0.25
    classes: [0, 1, 2, 3, 5, 7]
    class_thresholds:
      0: 0.20   # person - LOW (critical for safety)
      1: 0.25   # bicycle - LOW (modal split)
      2: 0.40   # car - HIGH (large, easy)
      5: 0.45   # bus - HIGH
      7: 0.45   # truck - HIGH
```

---

## Validation

### Baseline validation procedure

1. **Sampling windows**: 3 × 10-minute windows across lighting conditions
2. **Ground truth**: Human count from saved clip or live observation
3. **Compare**: False positives, false negatives, direction accuracy
4. **Targets**:
   - Daylight counting accuracy: ≥ 85%
   - Direction accuracy: ≥ 90%

### Continuous checks

- Re-validate after camera repositioning
- Re-validate after parameter changes
- Re-validate seasonally (lighting changes)

---

## Milestones

### ✅ Milestone 0 — Deployment Readiness

- [x] Runs headless without intervention
- [x] Auto-recovers from camera failures
- [x] Documented setup steps
- [x] Systemd service for Raspberry Pi

### ✅ Milestone 1 — Core Counting

- [x] Background subtraction detection
- [x] IoU-based tracking
- [x] Gate counting (two-line, bi-directional)
- [x] SQLite storage with count_events
- [x] Web interface (FastAPI + React)
- [ ] Validation procedure documented

### ✅ Milestone 2 — AI Detection

- [x] YOLO backend via Ultralytics (GPU/CPU)
- [x] Multi-class detection (person, bicycle, car, motorcycle, bus, truck)
- [x] Configurable detection backend (`bgsub`, `yolo`, `hailo`)
- [x] Hardware-aware logging (shows GPU name or CPU fallback)
- [x] Full pipeline integration (detection → tracking → counting → storage)
- [x] Schema v3 with class metadata (class_id, class_name, confidence, backend)
- [x] Class-specific confidence thresholds (improves pedestrian/bicycle detection)
- [ ] AI HAT+ (Hailo) backend for Raspberry Pi 5
- [ ] Improved tracking (ByteTrack-style)

**Detection Backend Capabilities:**

| Backend | Classification | Hardware | Pedestrian Detection | Status |
|---------|---------------|----------|---------------------|--------|
| `bgsub` | Single-class (motion blobs) | Any CPU | Poor (no classification) | ✅ Production |
| `yolo` | 6 classes + class-specific thresholds | GPU/CPU | Excellent (+300% vs single threshold) | ✅ Production |
| `hailo` | 6 classes + class-specific thresholds | Hailo NPU (Pi 5) | Excellent (planned) | ⏳ Planned |

All backends preserve class information through tracking → counting → storage.
Background subtraction produces unclassified detections (`class_id=NULL`, `class_name=NULL`).

**Class-Specific Thresholds**: YOLO backend uses two-stage filtering:
1. Run YOLO with low baseline threshold (0.25) to capture all detections
2. Apply class-specific thresholds post-detection: 0.20 for pedestrians/bicycles, 0.40-0.45 for vehicles
3. Result: Dramatically improved detection of small objects without increasing false positives

### ⏳ Milestone 3 — Speed Measurement

- [ ] Camera calibration procedure
- [ ] Ground-plane speed estimation
- [ ] Speed distribution statistics
- [ ] Validation against reference

### 🔄 Milestone 4 — Modal Split Analytics

- [x] Multi-class detection (via YOLO backend)
- [x] Class metadata stored in database (schema v3)
- [x] Class-based statistics API (`/api/stats/by-class`)
- [ ] Frontend display of modal split
- [ ] Class-specific time-of-day patterns
- [ ] Modal split reports (vehicles vs pedestrians vs cyclists)
- [ ] Validation procedure for class accuracy
- [ ] Time-lapse video generation for visual reports

### ⏳ Milestone 5 — Heatmaps

- [ ] Trajectory aggregation
- [ ] Time-bucketed occupancy grids
- [ ] Bird's-eye view transformation

### ⏳ Milestone 6 — Reliability & Monitoring

- [ ] Alerting for camera offline
- [ ] Disk usage monitoring
- [ ] Uptime tracking
- [ ] Cost controls for cloud

### ⏳ Milestone 7 — Advocacy Packaging

- [ ] Chart generation
- [ ] One-page summary template
- [ ] Before/after comparison tools
- [ ] CSV/PDF exports

---

## Operations

### Common commands

```bash
# Run headless
python src/main.py --config config/config.yaml

# Run with display (debug)
python src/main.py --config config/config.yaml --display

# Record video
python src/main.py --config config/config.yaml --record

# Stop running instance
python src/main.py --stop

# Replace existing instance (kill + start)
python src/main.py --config config/config.yaml --kill-existing

# Run tests
pytest tests/ -v
```

### Single Instance Enforcement

The system uses a PID file (`data/traffic_monitor.pid`) to ensure only one instance runs:

- `--stop`: Gracefully stops any running instance
- `--kill-existing`: Kills existing instance before starting new one
- Prevents port conflicts and duplicate counting

### Systemd service

```bash
sudo systemctl start traffic-monitor
sudo systemctl stop traffic-monitor
sudo systemctl status traffic-monitor
sudo journalctl -u traffic-monitor -f
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| No frames | Check camera connection, RTSP URL, credentials |
| Counts wrong | Re-check gate line placement, run validation |
| Cloud sync fails | Check GCP credentials, roles, bucket existence |
| High CPU | Reduce resolution/FPS, enable ROI cropping |

---

## Data Contracts

### CountEvent

```python
@dataclass
class CountEvent:
    track_id: int
    direction: str       # "A_TO_B" or "B_TO_A"
    direction_label: str # From config
    timestamp: float     # Unix time
    counting_mode: str   # "gate" or "line"
    gate_sequence: Optional[str]
    line_a_cross_frame: Optional[int]
    line_b_cross_frame: Optional[int]
    track_age_frames: int
    track_displacement_px: float
```

### API Response (CompactStatus)

```json
{
  "running": true,
  "last_frame_age_s": 0.5,
  "fps_capture": 30.0,
  "counts_today_total": 150,
  "counts_by_direction_code": {
    "A_TO_B": 80,
    "B_TO_A": 70
  },
  "direction_labels": {
    "A_TO_B": "northbound",
    "B_TO_A": "southbound"
  },
  "cpu_temp_c": 45.0,
  "disk_free_pct": 75.0,
  "warnings": []
}
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Camera drift | High | Stable mount, periodic framing checks |
| Night degradation | Medium | ROI tuning, IR illumination, accept daylight-only |
| Network outages | Medium | Local buffering, retry/backoff |
| Compute limits | Medium | Lower FPS/resolution, ROI cropping |
| Data accuracy | High | Validation procedure, ground truth comparison |
| GCP costs | Medium | Partition tables, limit uploads, spend alerts |

---

## Success Metrics

- **Operational**: >95% uptime over 30 days
- **Data quality**: Repeatable validation, documented error bounds, <10% counting error
- **Advocacy value**: Clear peak-hour patterns, shareable visuals, modal split breakdowns
- **Cost efficiency**: <$50/month GCP costs for continuous monitoring

---

## Open Questions

- Night handling: daylight-only accuracy acceptable, or invest in IR/better sensor?
- Speed method: zone-to-zone timing vs ground-plane calibration?
- Data retention: minimum retention for credible analysis?
- Multi-camera: support for multiple observation sources?
