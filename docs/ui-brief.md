# UI Build Brief (v1)

## Goal
Build a modern, component-based front end for the traffic measurement system that:
1) Shows “Is it working?” at a glance.
2) Allows configuring camera, zones/lines, detection sensitivity, and schedules.
3) Monitors device health (temp, storage, FPS, inference latency).

This is a local-first appliance UI running on a Raspberry Pi.

## Front-end framework (explicit choice)
- Use React + Vite + TypeScript.
- Use Tailwind CSS for styling.
- Use shadcn/ui for reusable UI components.
- Use lucide-react for icons.
- Use TanStack Query for data fetching and polling.
- Do NOT introduce Next.js or server-side rendering.
- Do NOT introduce heavy visualization frameworks beyond Recharts.

## Integration constraints
- FastAPI remains the backend.
- All API routes remain under /api/*.
- Frontend is built into static files and served by FastAPI.
- Live camera view must continue using MJPEG:
  /api/camera/live.mjpg
- UI must work fully offline on the local network.

## Repo structure to create
Add a new folder:

frontend/
  ├─ index.html
  ├─ vite.config.ts
  ├─ src/
  │   ├─ main.tsx
  │   ├─ App.tsx
  │   ├─ api/
  │   │   ├─ client.ts
  │   │   ├─ status.ts
  │   │   ├─ config.ts
  │   │   └─ health.ts
  │   ├─ components/
  │   │   ├─ StatusBar.tsx
  │   │   ├─ MjpegView.tsx
  │   │   ├─ CounterCard.tsx
  │   │   ├─ AlertBanner.tsx
  │   │   ├─ LineEditorCanvas.tsx
  │   │   └─ HealthCard.tsx
  │   ├─ pages/
  │   │   ├─ Dashboard.tsx
  │   │   ├─ Configure.tsx
  │   │   └─ Health.tsx
  │   └─ lib/
  │       └─ utils.ts

FastAPI must serve frontend/dist after build.

## Navigation
Top-level navigation:
- Dashboard (/)
- Configure (/config)
- Health (/health)
- Logs (/logs) (link to existing server-rendered page for now)

## Page requirements

### Dashboard
Purpose: Answer “Is it working?” in under 5 seconds.

Must include:
- Persistent status bar with:
  - RUNNING / DEGRADED / OFFLINE
  - Last frame age (seconds)
  - Capture FPS
  - Inference FPS
  - Inference latency p50/p95
  - CPU temperature
  - Disk free percentage
- Live MJPEG camera view
- Counter cards:
  - Today total
  - Last 15 minutes
  - Vehicles per minute
  - Direction breakdown (if available)
- Alerts:
  - Camera stale
  - Disk low
  - High temperature
  - Inference stalled

Data:
- Poll /api/status every 2 seconds.
- Status logic:
  - last_frame_age > 2s => degraded
  - last_frame_age > 10s => offline
  - disk_free_pct < 10 => warning
  - cpu_temp > 80C => warning

### Configure
Purpose: Safe configuration without editing YAML.

Must include:
- Camera settings:
  - Source type (CSI, USB, RTSP)
  - Resolution
  - FPS
  - Rotation
  - Inline “test feed” MJPEG preview
- Counting line editor:
  - Canvas overlay on a still frame
  - Drag two endpoints
  - Explicit direction mapping
- Detection settings:
  - Sensitivity / confidence threshold
  - Minimum object size
  - Tracking IoU threshold
- Schedule:
  - Enable/disable
  - Weekly active hours

Persistence:
- Load from GET /api/config
- Save via PUT or POST /api/config
- Save calibration data via /api/calibration if available

### Health
Purpose: Device truth and early failure detection.

Must include:
- CPU temp
- CPU usage
- RAM usage
- Disk usage
- Capture FPS
- Inference FPS
- Inference latency
- Uptime
- Camera last frame timestamp

Data:
- Poll /api/health every 5 seconds.

## API expectations
Prefer a single aggregate endpoint:

GET /api/status
Returns:
- running: boolean
- last_frame_age_s: number
- fps_capture: number
- fps_infer: number
- infer_latency_ms_p50
- infer_latency_ms_p95
- counts_today_total
- counts_by_direction
- cpu_temp_c
- disk_free_pct
- warnings: string[]

If /api/status does not exist, create it by aggregating existing endpoints.

## Non-goals (v1)
- No authentication
- No cloud UI
- No historical analytics beyond today
- No clip review UI yet

## Acceptance criteria
- UI loads in under 2 seconds on the Pi.
- Dashboard clearly shows running vs degraded vs offline.
- Configure page saves and persists values.
- Health page updates live and reflects real device state.
- No breaking changes to existing video or pipeline behavior.
