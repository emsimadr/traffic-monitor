# Traffic Monitor UI Revamp — Concept Document

**Status**: DRAFT FOR REVIEW  
**Date**: 2025-01-11  
**Prepared by**: Systems Architect

---

## Executive Summary

**Goal**: Revamp the web interface to create a modern, privacy-respecting command center that surfaces system health, counting accuracy, and traffic patterns in real-time—optimized for edge hardware and aligned with the Architect Constitution.

**Current state**:
- React/TypeScript frontend exists (`frontend/`) with Tailwind + shadcn/ui
- Modern dashboard with live feed, counts, status bar, system stats
- API client consuming `/api/status/compact`, `/api/stats/summary`, `/api/calibration`
- Legacy Jinja2 templates under `/legacy/*` routes

**Problem**:
- Frontend may be outdated vs recent architecture changes (observation layer, counting strategies, class-based detection)
- Missing visibility into **counting quality** (occlusions, fragmentation, detector confidence)
- Limited historical trend visualization (hourly/daily charts)
- Calibration workflow feels disconnected from live preview
- No clear indication of **privacy boundaries** (what's stored, what's not)

**Opportunity**:
Build a **command-center UI** that:
1. Shows system health and counting quality at a glance
2. Makes calibration intuitive and confidence-inspiring
3. Visualizes traffic patterns over time (without identifiable data)
4. Respects edge hardware constraints (minimal JS overhead)
5. Reinforces privacy principles in the UI (labels, tooltips, clear data retention policies)

---

## Design Principles (Constitution-Aligned)

### 1. Privacy-First Presentation
- Live feed shows **detection boxes only** (no faces, plates, identifiable features)
- UI labels emphasize aggregates: "Counts", "Patterns", "Flows"—never "Tracking" or "Surveillance"
- Clear indicators of what's stored locally vs cloud, retention windows
- No individual trajectory playback (aggregate heatmaps only)

### 2. Evidence-Grade Clarity
- Every metric has a tooltip explaining method and assumptions
- Calibration UI shows measurement uncertainty (e.g., "±2% typical error at 30mph")
- Historical charts include data quality indicators (frame drops, occlusions)
- Exportable reports for advocacy (CSV counts, aggregated speed distributions)

### 3. Edge-Optimized Performance
- Minimal JS bundle (<500KB gzipped)
- Prefer server-rendered charts for historical data (or lightweight Canvas/SVG)
- Live feed uses MJPEG (not WebRTC) to avoid heavy client processing
- Polling intervals respect edge hardware (2-5s for status, 30s for stats)

### 4. Observability as a Feature
- Dashboard surfaces failures prominently: camera offline, detector stalled, disk full
- Health page shows per-frame metrics: detection confidence, tracking continuity, inference latency
- Logs page streams real-time with severity filtering
- Config changes logged with timestamps and user attribution (if multi-user in future)

---

## User Flows & Required UI Elements

### Flow 1: First-Time Setup (Calibration)
**Actors**: Operator setting up a new deployment

**Steps**:
1. Navigate to `/calibration`
2. See live MJPEG feed with camera transform controls (rotate, flip, swap R/B)
3. Toggle between **Line Counter** and **Gate Counter** modes
4. **If Line Counter**: Click two points to define line, see direction indicator (A→B vs B→A)
5. **If Gate Counter**: Click four points to define Line A and Line B, see direction labels (A_TO_B, B_TO_A)
6. Adjust parameters: `min_age_frames`, `min_displacement_px`, `max_gap_frames`
7. See **live validation**: counts update in real-time, UI shows "Double-count protection: ACTIVE"
8. Save → UI confirms persistence to `config/config.yaml`
9. Option to test calibration: watch 5 vehicles cross, verify counts match manual count

**UI Elements**:
- `<CalibrationWorkflow />` component with step-by-step wizard
- Interactive canvas overlay for line/gate drawing (reuse legacy logic)
- Parameter sliders with tooltips explaining each setting
- Live count preview card (last 5 min counts)
- Validation indicator: "✓ Gate lines valid" or "⚠ Lines too close (<10px gap)"

**Risks mitigated**:
- **Accuracy**: Real-time feedback prevents misconfigured gates
- **Privacy**: No identifiable data shown, just bounding boxes

---

### Flow 2: Daily Monitoring (Dashboard)
**Actors**: Operator checking system health and traffic trends

**Steps**:
1. Land on `/` (Dashboard)
2. Top status bar shows: RUNNING/OFFLINE, FPS, frame age, CPU temp, disk space, today's count
3. Main grid:
   - **Live Feed** (left 2/3): MJPEG stream with gate lines overlaid
   - **Counts Card** (right 1/3): Today's total, by-direction breakdown, hourly mini-chart
4. Bottom row:
   - **Alerts** (if any): "⚠ Disk <20%", "⚠ Camera stale (5s)", "⚠ Temp >70°C"
   - **System Stats**: Inference FPS, latency (p50/p95), detector backend, model name
   - **Recent Events**: Last 10 count events with timestamps and direction (no images)
5. Click on hourly mini-chart → expands to full Historical page with 7/30/90-day views

**UI Elements**:
- `<StatusBar />` (existing, may need updates)
- `<LiveFeed />` with server-rendered gate line overlay (consider drawing lines client-side from config for responsiveness)
- `<CountsCard />` with Recharts mini-sparkline (hourly counts)
- `<AlertsList />` with severity colors (red=critical, amber=warning)
- `<SystemStatsCard />` with detector backend badge ("YOLO v8n CPU" or "Hailo-8L")
- `<RecentEventsTable />` (new): timestamp, direction label, class (vehicle/bike), confidence

**Risks mitigated**:
- **Performance**: Minimal JS (MJPEG + polling), no WebRTC or canvas processing
- **Observability**: Failures surface immediately

---

### Flow 3: Historical Analysis (Trends)
**Actors**: Operator or advocate preparing a report

**Steps**:
1. Navigate to `/trends` (new page)
2. See time-range picker: Last 24h, 7d, 30d, 90d, Custom
3. Top charts:
   - **Hourly Counts**: Bar chart, direction-stacked, shows diurnal patterns
   - **Daily Totals**: Line chart, smooth trendline, highlights anomalies (2σ outliers)
4. Middle section:
   - **Direction Breakdown**: Pie or donut chart (last 7d)
   - **Class Distribution**: Bar chart (vehicles vs bikes vs pedestrians, if class detection enabled)
5. Bottom: **Data Quality** timeline (frame drops, occlusion events, detector confidence ranges)
6. Export button: CSV download (date,hour,direction,count,class) for external analysis

**UI Elements**:
- `<TrendsPage />` (new)
- `<TimeRangePicker />` with presets and custom date inputs
- `<HourlyCountsChart />` (Recharts BarChart, stacked by direction)
- `<DailyTotalsChart />` (Recharts LineChart with error bands)
- `<DirectionBreakdownChart />` (Recharts PieChart or simple bars)
- `<DataQualityTimeline />` (Canvas or SVG heatmap: green=good, amber=degraded, red=offline)
- `<ExportButton />` generates CSV via `/api/stats/export?start=...&end=...`

**Risks mitigated**:
- **Evidence-grade**: Data quality timeline shows when counts are less reliable
- **Privacy**: No individual trajectories, only aggregates

---

### Flow 4: Configuration (Advanced)
**Actors**: Operator tuning detector or storage settings

**Steps**:
1. Navigate to `/config`
2. See tabbed interface:
   - **Counting**: Mode (line/gate), direction labels, parameters (already in Calibration, but here for reference)
   - **Detection**: Backend (BgSub/YOLO/Hailo), model path, confidence threshold, classes to detect
   - **Storage**: Local DB path, cloud sync enabled, retention policy (days)
   - **Camera**: Resolution, FPS, RTSP transport (tcp/udp)
3. Edit YAML overrides inline with syntax highlighting
4. Save → UI shows diff preview ("+ detection.backend: yolo"), then applies changes
5. Restart prompt if needed (e.g., changing detector backend)

**UI Elements**:
- `<ConfigPage />` with `<Tabs />` (existing shadcn component)
- `<YAMLEditor />` (use `monaco-editor` or `react-simple-code-editor` with YAML syntax)
- `<ConfigDiff />` modal showing before/after
- `<RestartBanner />` if config changes require pipeline restart

**Risks mitigated**:
- **Schema**: Diff preview prevents accidental data model changes
- **Edge-first**: UI warns if cloud sync disabled (doesn't block)

---

### Flow 5: Health & Diagnostics (Troubleshooting)
**Actors**: Operator debugging frame drops or detector issues

**Steps**:
1. Navigate to `/health`
2. See three sections:
   - **Pipeline Status**: Observation → Detection → Tracking → Counting → Storage (green/amber/red indicators)
   - **Frame Metrics**: FPS (capture vs infer), latency histogram (p50/p95/p99), dropped frames (last hour)
   - **System Resources**: CPU %, memory MB, disk I/O, temperature, uptime
3. Click "View Logs" → opens `/logs` page with real-time stream (last 200 lines, auto-scroll)
4. Logs filterable by severity: DEBUG, INFO, WARN, ERROR

**UI Elements**:
- `<HealthPage />` (existing, needs expansion)
- `<PipelineDiagram />` (visual flow with status indicators on each node)
- `<FrameMetricsChart />` (Recharts histogram or sparklines)
- `<ResourceGauges />` (circular progress for CPU/mem/disk)
- `<LogsViewer />` (existing, add severity filter buttons)

**Risks mitigated**:
- **Observability**: Pipeline diagram makes failures obvious
- **Performance**: Logs tail via API, not streamed over WebSocket (simpler for edge)

---

## Visual Design: Command Center Aesthetic

### Color Palette (Dark Mode)
- **Background**: `#0b0f14` (nearly black)
- **Surface**: `#111827` (cards)
- **Border**: `#1f2a37` (subtle dividers)
- **Text**: `#e8eef6` (high contrast primary), `#9fb0c3` (muted secondary)
- **Accent**: `#2563eb` (blue, primary actions), `#00c9ff` (cyan, Line A), `#ff6347` (orange-red, Line B)
- **Status**: `#22c55e` (green, running), `#f59e0b` (amber, warning), `#ef4444` (red, error)

### Typography
- **Headings**: `font-family: system-ui, -apple-system, sans-serif`; `font-weight: 700`
- **Body**: `14px`, `line-height: 1.5`, tracking slightly loose for readability
- **Monospace**: `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas` for logs/config

### Layout
- **Sidebar nav** (left, collapsed on mobile): Dashboard, Trends (new), Calibration, Config, Health, Logs
- **Top bar**: System name + deployment location (configurable), global status pill, quick actions (restart, export)
- **Bottom status bar** (existing): Running/offline, FPS, temp, disk, today's count, warnings badge

### Components (shadcn/ui + custom)
- **Cards**: Rounded corners (`12px`), subtle borders, gradient accents for emphasis (e.g., Today's count)
- **Charts**: Recharts with dark theme, minimal gridlines, tooltips on hover
- **Live feed**: 16:9 aspect ratio, rounded corners, gate lines drawn with `stroke-dasharray` for visual distinction
- **Buttons**: Primary (blue), secondary (slate), danger (red), all with hover states
- **Badges**: Pill-shaped for status (`RUNNING`, `OFFLINE`), square for counts (`A→B: 142`)

---

## Implementation Plan (High-Level)

### Phase 1: Audit & Sync (1-2 days)
1. **Audit API endpoints**: Ensure `/api/status/compact`, `/api/stats/summary`, `/api/calibration` return expected shapes
2. **Add missing endpoints**: `/api/stats/export`, `/api/status/pipeline`, `/api/stats/hourly?days=7`
3. **Update API client** (`frontend/src/lib/api.ts`): Add new types and fetch functions
4. **Test with Postman/curl**: Validate all endpoints work with current backend

**Deliverable**: API contract document (types, endpoints, examples)

### Phase 2: Dashboard Enhancements (2-3 days)
1. **Live feed improvements**: Add client-side gate line drawing from config (avoids baking into MJPEG)
2. **Counts card**: Add mini-sparkline for hourly trends (last 24h)
3. **Recent events table**: Fetch last 10 count events from `/api/stats/recent` (new endpoint)
4. **System stats card**: Add detector backend badge, inference latency percentiles
5. **Alerts list**: Expand with actionable suggestions ("Free up disk space", "Check camera RTSP URL")

**Deliverable**: Updated Dashboard page with richer observability

### Phase 3: Trends Page (3-4 days)
1. **New `/trends` route**: Time-range picker, hourly/daily charts, direction/class breakdowns
2. **Data quality timeline**: Fetch frame drop events from `/api/stats/quality?start=...&end=...` (new endpoint)
3. **Export feature**: CSV button → downloads data via `/api/stats/export`
4. **Responsive design**: Charts stack on mobile, legend toggles

**Deliverable**: Trends page with historical analysis tools

### Phase 4: Calibration Workflow (2-3 days)
1. **Redesign `/calibration`**: Step-by-step wizard (Camera → Lines → Parameters → Test → Save)
2. **Interactive line drawing**: Reuse legacy canvas logic, modernize with React hooks
3. **Live validation**: Fetch `/api/stats/live` to show counts updating in real-time
4. **Parameter tooltips**: Explain `min_age_frames`, `min_displacement_px`, `max_gap_frames` with examples
5. **Test mode**: Button to "Watch 5 vehicles" and compare manual vs automated counts

**Deliverable**: Intuitive calibration wizard

### Phase 5: Config & Health Pages (2 days)
1. **Config page**: Tabbed editor with YAML syntax highlighting, diff preview modal
2. **Health page**: Pipeline diagram, frame metrics charts, resource gauges
3. **Logs page**: Severity filter buttons, auto-scroll toggle, timestamp formatting

**Deliverable**: Complete admin tooling

### Phase 6: Polish & Performance (1-2 days)
1. **Bundle size audit**: Ensure <500KB gzipped (use `webpack-bundle-analyzer`)
2. **Accessibility**: ARIA labels, keyboard navigation, focus states
3. **Mobile testing**: Verify all pages usable on tablet/phone
4. **Error boundaries**: Graceful fallbacks if API fails
5. **Dark mode refinement**: Adjust contrast ratios for WCAG AA compliance

**Deliverable**: Production-ready UI

---

## API Endpoints Status (Phase 1 Complete ✅)

### ✅ Implemented (Phase 1)
- `GET /api/stats/recent?limit=50` → Recent count events (timestamp, direction, class, confidence)
- `GET /api/stats/hourly?days=7` → Hourly counts with by_direction and by_class breakdowns
- `GET /api/stats/daily?days=30` → Daily counts with by_direction and by_class breakdowns
- `GET /api/stats/export?start=...&end=...&format=csv` → CSV download of count events
- `GET /api/status/pipeline` → Pipeline health (each stage: running/degraded/offline)
- `GET /api/status/compact` → Enhanced with `counts_by_class` field
- `GET /api/stats/by-class` → Already existed, returns class breakdown for time range

### 🔮 Deferred (Future)
- `GET /api/stats/quality?start=...&end=...` → Frame drop events, occlusions (requires metrics collection in pipeline)
- `GET /api/calibration` validation → Add `validation_status` (requires gate line validation logic)

### 📝 Notes
- All endpoints privacy-safe (no PII, aggregates only)
- Performance optimized (query limits, indexes)
- Backward compatible with existing frontend

---

## Privacy & Data Retention (UI Reinforcement)

### Dashboard Indicators
- **Live feed banner**: "Live preview only • Not recorded • Privacy-preserving detection"
- **Retention policy card**: "Local DB: 365 days • Cloud sync: aggregates only • No identifiable data"

### Settings Page
- **Privacy section**: Toggle for raw video retention (default: OFF, 7-day max if ON)
- **Data export**: CSV only includes counts, not images or trajectories
- **Cloud sync**: Clearly labeled "Aggregates only (hourly counts, no raw detections)"

### Tooltips
- Hover over "Direction A→B" → "Based on crossing sequence • No identity tracked"
- Hover over "Class: vehicle" → "Category only • License plates never captured"

---

## Validation Criteria

### Functional
- [ ] All pages load in <2s on Raspberry Pi 4
- [ ] Live feed streams at 5-10 FPS (configurable)
- [ ] Calibration workflow saves valid config to YAML
- [ ] Historical charts render 90 days of data without lag
- [ ] CSV export downloads within 5s for 1 year of data
- [ ] Logs page auto-updates every 5s with new entries
- [ ] Alerts appear <5s after condition triggered (e.g., disk <20%)

### Non-Functional
- [ ] JS bundle <500KB gzipped
- [ ] Lighthouse score >90 (performance, accessibility)
- [ ] Works in Chrome, Firefox, Safari (latest 2 versions)
- [ ] Responsive on screens ≥768px width
- [ ] No console errors in production build
- [ ] All privacy labels and tooltips in place

### Privacy
- [ ] No identifiable data visible in UI (no faces, plates, trajectories)
- [ ] Retention policy clearly stated in Settings
- [ ] Live feed includes privacy banner
- [ ] CSV exports contain only aggregates

### Evidence-Grade
- [ ] Every metric has a tooltip explaining method
- [ ] Data quality timeline shows when counts are less reliable
- [ ] Calibration wizard includes validation step
- [ ] Historical charts include error bands or confidence intervals

---

## Open Questions for Review

1. **Trends page**: Should we include speed distribution charts (if speed measurement is implemented), or defer to future milestone?
2. **Multi-camera support**: Current UI assumes single camera. If multi-camera is planned, should nav sidebar list cameras or use a dropdown switcher?
3. **User roles**: Constitution doesn't mention auth. Should we add basic HTTP auth or leave open for now?
4. **Heatmaps**: Planned in PLAN.md ("where traffic actually flows over time"). Should this be a tab on Trends page or separate `/heatmaps` route?
5. **Real-time alerts**: Should UI support browser notifications for critical alerts (e.g., camera offline >1min), or just in-page badges?
6. **Class detection**: Current UI assumes class-aware detection (vehicle/bike/pedestrian). Is this implemented backend-side with YOLO, or should UI hide class UI for BgSub mode?

---

## Summary

This concept proposes a **command-center UI** that balances modern aesthetics with edge performance, respects privacy principles, and surfaces counting quality/system health prominently. The implementation phases are incremental (Dashboard → Trends → Calibration → Config/Health), allowing review and adjustment at each stage.

**Next steps**:
1. Review this concept with stakeholders
2. Answer open questions
3. Prioritize phases (MVP = Phase 1+2, Full = all 6 phases)
4. Proceed with Phase 1 (API audit & sync)


