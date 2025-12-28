# Neighborhood Traffic Monitoring System — Plan

This `PLAN.md` is the living roadmap for building a **privacy-respecting, evidence-grade** traffic monitoring system that runs on an edge device (e.g., Raspberry Pi) and optionally syncs summarized results to Google Cloud.

---

## Project Overview

### What we’re building

- A system that continuously captures a street-facing video stream, detects and tracks traffic participants, and records counts (and later: speed distributions, vulnerable road users, and movement patterns).
- A hybrid architecture:
  - **Edge**: real-time detection + local buffering/storage so data collection continues without internet.
  - **Cloud (optional)**: long-term storage and analytics (BigQuery) + artifacts (Cloud Storage) to support dashboards and advocacy.

### Scope and non-goals (important)

**In scope (near term):**

- Vehicle counting with direction and time-of-day patterns.
- Speed measurement with a documented, repeatable calibration/validation process.
- Privacy-first summaries suitable for sharing externally.
- Heatmaps that show where traffic actually flows over time.

**Explicit non-goals (unless you later choose otherwise):**

- Identifying individuals, license plates, or faces.
- Real-time enforcement or “catching” specific drivers.
- Storing continuous raw video long-term (short validation clips only, by default).

### Why it matters (core motivation)

We need **credible quantitative evidence** (counts, patterns, and eventually speeds and conflicts) to support traffic calming advocacy and to withstand scrutiny from municipal stakeholders—without turning the project into surveillance.

### What’s already implemented (current repo status)

Milestone 1 foundation exists and now includes a FastAPI web UI:

- **Capture (current)**: USB camera index or RTSP URL, with retry logic (`src/camera/capture.py` / `src/camera/backends/opencv.py`).
- **Detection**: background-subtraction-based vehicle detection (`src/detection/vehicle.py`).
- **Tracking**: IoU-based tracking to maintain vehicle trajectories across frames (`src/detection/tracker.py`); configurable via `tracking` section (max_frames_since_seen, min_trajectory_length, iou_threshold).
- **Counting**: Gate-based counting using two lines (A and B) to determine direction (`src/analytics/counter.py`); vehicles are counted when crossing both gates in sequence (A→B or B→A).
- **Storage**: SQLite + hourly/daily aggregates + retention cleanup (`src/storage/database.py`).
- **Cloud sync (optional)**: periodic background sync to BigQuery + video sample upload to Cloud Storage (`src/cloud/sync.py`).
- **Web UI (current)**: FastAPI + Jinja templates + React frontend, MJPEG live view with overlayed gate lines, stats summary, config editor, calibration page, and logs (`src/web/` + `frontend/`). Served via Uvicorn in a background thread from `src/main.py`.

---

## Hardware and Deployment Target (AI-first)

This section reflects the **target deployment** you want to move to. Where something is not yet implemented in code, it is explicitly marked as “planned.”

### Primary target hardware

- Raspberry Pi 5 (16GB)
- Raspberry Pi AI HAT+ (Hailo-8 class accelerator)
- Raspberry Pi Camera Module 3 Wide (CSI)
- Active cooling + stable 5V power supply (headroom for sustained load)
- Storage: high-endurance microSD; optional USB SSD later for clip/artifact retention

### Camera strategy

- **Default (planned)**: CSI camera via `Picamera2` / libcamera pipeline (lower overhead, better stability on Pi).
- **Fallback (current)**: USB webcam or RTSP IP camera via OpenCV (`src/camera/capture.py`).

### Detection strategy

- **Default (planned)**: YOLO-family detector on the AI HAT+ backend.
- **Fallback (current)**: classical CV background subtraction (`src/detection/vehicle.py`) for baseline comparison and troubleshooting.

---

## How the System Works (today)

This section is intended to be “handoff-friendly” for someone new.

### Runtime flow

- `src/main.py` loads `config/config.yaml` (and `config/cloud_config.yaml` if present), configures logging, then runs an infinite frame loop.
- Each frame:
  - is read from `create_camera` (USB/RTSP; retry/backoff),
  - is passed to `VehicleDetector.detect()` (background subtraction + morphological cleanup + contour filtering + heuristics; YOLO when enabled),
  - produces bounding boxes which are fed to `VehicleTracker.update()` for IoU-based tracking, then to `GateCounter.process()` for gate-based counting,
  - writes counted crossings into SQLite (`vehicle_detections`) and periodically updates aggregates (`hourly_counts`, `daily_counts`).
- If cloud is enabled, a background thread periodically syncs unsynced rows to BigQuery and can upload occasional video samples to Cloud Storage.
- A FastAPI web server (Uvicorn) runs in a background thread, serving:
  - Live MJPEG with overlayed gate lines (`/api/camera/live.mjpg` + canvas overlay in dashboard)
  - Stats endpoints (`/api/stats/*`) and a summary dashboard
  - Config editor and calibration routes (`/config`, `/calibration`, `/api/config`, `/api/calibration`)
  - Logs viewer (`/logs`, `/api/logs/tail`)

### Detection heuristics already in play (so we don’t forget them)

- Road-area filter: detection centers must be between ~20% and ~95% of frame height.
- Stationary-object filter: removes boxes that don’t move more than a small threshold between frames.
- Box merging: merges nearby/overlapping detections to reduce fragmentation.

---

## How the System Works (target runtime flow — planned)

This is the intended “default path” once the Pi 5 + AI HAT+ stack is wired in, while keeping classical CV as a fallback.

### Planned runtime flow

- `src/main.py` loads `config/config.yaml` (and `config/cloud_config.yaml` if present), configures logging, then runs an infinite loop.
- Each frame (or every Nth frame if frame-skipping is enabled):
  1. **Capture**: read frame from CSI camera (preferred) or RTSP/USB fallback, with retry/backoff.
  2. **Preprocess**: apply ROI cropping and optional resize.
  3. **Detect**: run a YOLO-family detector using the active backend:
     - Primary backend (planned): AI HAT+ (Hailo runtime)
     - Dev/fallback backend (planned): CPU (baseline / portability)
  4. **Track**: detection-driven tracker (planned upgrade):
     - ByteTrack-style association (high/low confidence matching)
     - Track lifecycle (tentative → confirmed → lost → removed)
  5. **Analytics**:
     - Counting: gate crossings with direction (+ class once available)
     - Speed (planned): calibrated ground-plane displacement over time
     - Heatmap (planned): time-bucketed occupancy grids (image-plane quick mode; bird’s-eye preferred)
  6. **Persist**:
     - Store privacy-minimized events + aggregates to SQLite
     - Optionally retain short validation clips and calibration artifacts with retention rules
  7. **Cloud sync (optional)**:
     - Periodic sync to BigQuery
     - Optional upload of validation artifacts to Cloud Storage

---

## Problems to Solve

### Data quality & credibility

- **Counting accuracy**: avoid double counts, missed detections, and shadow/lighting artifacts.
- **Direction correctness**: ensure “northbound/southbound” mapping matches real-world direction.
- **Calibration & speed**: define an approach for speed measurement that is defensible and repeatable.

### Reliability & operations

- **24/7 stability**: handle camera dropouts, reboots, network interruptions, and storage limits.
- **Safe upgrades**: configuration changes should not break long-running deployments.
- **Observability**: logs, health indicators, and lightweight alerting for failures.

### Privacy & community trust

- **Minimize sensitive data**: avoid collecting identifiable imagery by default.
- **Retention policy**: only keep raw video when necessary (e.g., short samples for validation), and expire it.
- **Transparency**: clear communication of what is collected and why.

### Advocacy outputs

- **Stakeholder-ready summaries**: charts and narratives that clearly show the problem (volumes, peaks, speeding frequency, etc.).
- **Before/after comparisons**: ability to compare conditions around interventions (signage, speed bumps, etc.).
 - **Heatmap credibility**: produce visuals that are compelling but also defensible (image-plane vs bird’s-eye).

---

## Assumptions & Constraints

- **Fixed camera**: the counting gate and ROI assume a stable mount; even small shifts can change counts.
- **Environment variability**: sun/shadows/rain/night impact all methods; AI detectors are typically more robust than background subtraction but still need validation.
- **Edge compute**: Raspberry Pi class hardware may require lower FPS, lower resolution, and ROI cropping for stability.
- **Time accuracy**: timestamps are system time; if the device clock drifts, day/hour aggregations drift too (consider NTP).
- **Privacy posture**: default should be “store minimal data needed for evidence,” not “store everything just in case.”

---

## Choices to Be Made (Decisions)

These are the key decisions that affect architecture, cost, and credibility. Each should be decided and recorded before expanding scope.

### Camera and placement

- **Camera type**:
  - Option A (planned default): CSI camera (Picamera2/libcamera)
  - Option B: RTSP IP camera (long cable-free placements; supported today)
  - Option C: USB webcam (simple, local; supported today)
- **Mounting/angle**:
  - Choose: view covering lanes + a clear counting gate region with minimal occlusion.
- **Night strategy**:
  - Choose: accept reduced accuracy at night vs add IR illumination vs use higher-sensitivity camera.

### Counting gate semantics

- **Gate geometry**:
  - The system uses two gate lines (A and B) to form a counting zone
  - Lines can be horizontal, diagonal, or any orientation
  - Vehicles are counted when they cross both gates in sequence (A→B or B→A)
- **Direction mapping**:
  - A→B transition maps to one direction label (e.g., "northbound")
  - B→A transition maps to the opposite direction label (e.g., "southbound")
  - Labels are configurable via `counting.direction_labels` in config

### Detection approach (now vs later)

- **Now (baseline)**: background subtraction + contour filtering (already implemented).
- **Planned default**: YOLO-family detection (AI HAT+; CPU fallback for development).
- **Later options**:
  - Option A: classical CV improvements (morphology, perspective ROI, adaptive thresholds)
  - Option B: upgraded tracking (ByteTrack) and calibration-driven analytics

### Speed measurement methodology

- **Option A (defensible, moderate complexity)**: calibrated ground-plane + track displacement over time.
- **Option B (simple, less accurate)**: zone-to-zone timing between two reference lines.
- **Choice needed**: which method meets “city-scrutiny” requirements with acceptable effort.

### Cloud posture (cost & governance)

- **Cloud mode**:
  - Option A: local-only (no internet required; simplest privacy)
  - Option B: sync aggregates + detections to BigQuery (supported today)
  - Option C: store raw video in cloud (not recommended by default)
- **Cost controls**:
  - Choose: retention windows, sampling rate for video, BigQuery partitioning strategy, alerting thresholds.

### Data model boundaries

- **What is a “detection event”?** (currently: each counted crossing with timestamp + direction)
- **What should be aggregated?** (hourly/daily counts are implemented; decide weekly/monthly + peak hour summaries)
- **What “evidence artifacts” do we keep?** (e.g., calibration images, short validation clips)

---

## Data Contracts (Schemas & Meaning)

This is the contract between edge capture/detection and downstream analytics. Keep it stable; version it when it changes.

### SQLite tables (implemented)

- **`vehicle_detections`**
  - **Meaning**: one row per counted crossing of the counting gate (not one row per frame detection).
  - **Key fields**:
    - `timestamp` (REAL): unix epoch seconds
    - `date_time` (TEXT): human-readable timestamp
    - `direction` (TEXT): gate crossing direction code (e.g., `"A_TO_B"` or `"B_TO_A"`)
    - `direction_label` (TEXT): human-readable label (e.g., `"northbound"` or `"southbound"`)
    - `cloud_synced` (INTEGER): 0/1

- **`hourly_counts`**
  - **Meaning**: derived hourly totals computed from `vehicle_detections`.
  - **Key fields**: `hour_beginning`, `vehicle_count`, `cloud_synced`

- **`daily_counts`**
  - **Meaning**: derived daily totals computed from `vehicle_detections`.
  - **Key fields**: `date`, `vehicle_count`, `cloud_synced`

### BigQuery tables (implemented when cloud enabled)

BigQuery tables mirror the SQLite tables above (via `src/cloud/sync.py`), with the same semantic meaning.

---

## Recommended Data Model Additions (planned; privacy-preserving)

These additions enable class counts, speed distributions, and heatmaps without storing per-frame imagery.

- **`track_summaries` (planned)**:
  - One row per completed track (not per frame)
  - Suggested fields: `start_ts`, `end_ts`, `class`, `direction`, `min_conf`, `track_length_frames`, `mean_speed`, `p95_speed`, `speed_confidence`

- **`speed_aggregates` (planned)**:
  - Time-bucketed distributions by class/direction
  - Suggested fields: `bucket_start`, `class`, `direction`, `n`, `median`, `p85`, `p95`, `pct_over_limit`

- **`heatmap_tiles` (planned)**:
  - Time-bucketed compressed grids + metadata
  - Suggested fields: `bucket_start`, `class`, `mode` (`image_plane|birdseye`), `grid_blob`, `grid_metadata_json`

---

## Validation & QA (How we know the numbers are trustworthy)

If this project is used for advocacy, validation is not optional.

### Baseline validation procedure (recommended)

- **Pick sampling windows**: e.g., 3 × 10-minute windows across different lighting conditions.
- **Ground truth**: human count crossings from a short saved clip or live observation.
- **Compare**:
  - False positives (system counted, human did not)
  - False negatives (human counted, system did not)
  - Direction accuracy
- **Acceptable targets (initial)**:
  - Daylight vehicle counting accuracy: target ≥ 85% (tune thresholds/ROI until achieved)
  - Direction accuracy: target ≥ 90% in validated windows

### Continuous drift checks

- Re-run a short validation sample after any camera repositioning, seasonal lighting change, or parameter tuning.

---

## Milestones (AI-first reordered, with Done Criteria)

Milestones are ordered to maximize advocacy value early while keeping scope controlled.

### Milestone 0 — Deployment readiness

**Goal**: make the system safe to run unattended.

**Done criteria**:
- Runs headless for 72 hours without manual intervention.
- Auto-recovers from camera read failures and network outages.
- Documented setup steps (camera, config, secrets, startup).

### Milestone 1 — AI-based detection + robust tracking + core counting

**Goal**: counting by class and direction is credible and stable.

**Done criteria**:
- YOLO backend active (CPU baseline in dev; AI HAT+ on device).
- Tracking prevents double counts (upgrade path: ByteTrack-style association).
- Counts recorded in SQLite; aggregates maintained.
- Cloud sync works when enabled; local-only mode works when disabled.
- Validation procedure exists and targets are met.

### Milestone 2 — Speed measurement (calibrated)

**Goal**: produce speed distributions and speeding rates.

**Done criteria**:
- Camera calibration documented and repeatable.
- Speed estimates validated against a reference method (e.g., radar sign / pacing / known-distance timing).
- Speed histogram + percentile summaries available (local export and/or BigQuery).

### Milestone 3 — Pedestrian detection (privacy-first)

**Goal**: quantify vulnerable road user exposure without identification.

**Done criteria**:
- Pedestrian counts and time-of-day patterns captured with acceptable accuracy in daylight.
- Privacy policy documented (no identity, no face recognition, minimal retention of raw imagery).

### Milestone 4 — Bicycle detection

**Goal**: quantify cycling volumes and patterns (where feasible).

**Done criteria**:
- Bicycle counts available and distinguished from pedestrians/vehicles with acceptable error rate.
- Dashboards can show modal split (vehicle vs pedestrian vs bicycle).

### Milestone 5 — Paths/heatmaps (optional, evidence enhancer)

**Goal**: time-bucketed movement heatmaps; bird’s-eye preferred once calibration exists.

**Done criteria**:
- Track trajectories can be aggregated into coarse heatmaps without storing identifiable imagery.
- Heatmaps are stable enough to show patterns across days/weeks.

### Milestone 6 — Reliability, monitoring, and cost controls

**Goal**: make long-term operation cheap and boring.

**Done criteria**:
- >95% uptime over 30 days.
- Clear alerting for camera offline / sync failure / disk usage.
- Retention policies enforced for local and cloud data.

### Milestone 7 — Advocacy packaging

**Goal**: turn data into stakeholder-ready materials.

**Done criteria**:
- A standard set of charts and a “one-page summary” can be generated for a chosen time window.
- Before/after comparison process defined and repeatable.
- Exports suitable for sharing (CSV + PDF/slide-ready images).

---

## Operations Runbook (Practical “how to run this”)

### Configuration files

- `config/config.yaml`: camera source, resolution/FPS, detection thresholds, counting gate (line_a, line_b, direction_labels), retention, logging.
- `config/cloud_config.yaml`: GCP project/bucket/dataset/table names and sync interval/retry settings.
- `secrets/`:
  - `camera_secrets.yaml` (if using RTSP credentials injection)
  - `gcp-credentials.json` (service account key; keep out of git)

### Common commands

- **Run headless**: `python src/main.py --config config/config.yaml`
- **Run with display** (debug): `python src/main.py --config config/config.yaml --display`
- **Record samples** (validation): `python src/main.py --config config/config.yaml --record`
- **Test camera**: `python tools/test_camera.py --device 0`
- **Test cloud**: `python tools/test_cloud_connection.py --config config/cloud_config.yaml`

### What to do when something goes wrong

- **No frames / intermittent frames**: verify RTSP URL, credentials injection, try switching RTSP transport TCP/UDP, check network stability.
- **Counts suddenly change**: likely camera moved; re-check gate line placement and rerun validation sampling.
- **Cloud sync errors**: verify credentials, bucket/dataset existence, service account roles, and review `logs/traffic_monitor.log`.

---

## Timeline (rough)

This can be re-estimated once Milestone 0 “deployment readiness” is validated in the real environment.

- Milestone 0: 1–2 weeks
- Milestone 1: 0–1 week (mostly complete; focus on validation + docs)
- Milestone 2: 2–4 weeks
- Milestone 3–4: 3–6 weeks (depending on method)
- Milestone 5: 2–5 weeks (optional)
- Milestone 6: ongoing hardening during all milestones
- Milestone 7: 1–3 weeks

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Camera obstruction / angle drift | High | Stable mount; periodic framing checks; calibration checklist |
| Lighting/night degradation | Medium–High | ROI tuning; optional IR; accept “daylight-only” metrics initially |
| Network outages | Medium | Local buffering (already); retry/backoff (already) |
| Compute limits on Raspberry Pi | Medium | Lower FPS/resolution; ROI cropping; consider DNN only if needed |
| Privacy concerns | High | Default to aggregates; short validation clips only; retention limits; transparency |
| GCP costs | Medium | Store aggregates; partition tables; limit video uploads; alerts on spend |

---

## Success Metrics (Definition of “this worked”)

- **Operational**: >95% uptime over 30 days; data collected through outages/reboots.
- **Data quality**: repeatable validation method; documented expected error bounds.
- **Advocacy value**: clear peak-hour patterns; (later) speeding distribution + shareable visuals.
- **Privacy**: no identity tracking; minimal video retention; documented policy and configuration defaults.

---

## Open Questions (Capture decisions here as you learn)

- **Direction semantics**: does the current “northbound/southbound” mapping match the real street directions for your camera view?
- **Night handling**: do we accept “daylight-only” accuracy for advocacy, or invest in IR / a better sensor / a DNN detector?
- **Speed method**: zone-to-zone timing vs ground-plane calibration—what level of accuracy is needed to convince your city?
- **Data retention**: what’s the minimum retention that still supports credible analysis and audits?
