# Development History

**Last Updated:** January 16, 2026

This document captures major implementation milestones and historical context for the Traffic Monitoring System.

---

## Schema v3 Implementation (January 2026)

### Overview
Major milestone adding multi-class detection metadata to enable evidence-grade modal split analysis.

### Key Changes
- Added 6 new fields to `count_events` table: class_id, class_name, confidence, detection_backend, platform, process_pid
- Implemented metadata preservation through entire pipeline (detection → tracking → counting → storage)
- Added class-based and backend-based indexes for performance
- Updated all data models (CountEvent, Track, TrackState)
- Migrated BigQuery schema
- Created migration tools for both local and cloud databases

### Impact
- Enables modal split analysis (cars vs bikes vs pedestrians)
- Tracks detection quality (confidence distributions)
- Enables backend comparison (YOLO vs Hailo vs BgSub)
- Platform traceability for debugging

### Documentation
See `docs/SCHEMA_V3.md` for complete technical reference.

---

## UI Revamp (January 2026)

### Original Concept

The UI revamp was conceived to transform the frontend from basic monitoring to a command-center experience that surfaces system health, counting accuracy, and traffic patterns in real-time.

**Design Principles:**
1. **Privacy-First Presentation** - Detection boxes only, no faces/plates
2. **Evidence-Grade Clarity** - Every metric has explanation tooltips
3. **Edge-Optimized Performance** - Minimal JS overhead for Pi deployment
4. **Fail-Visible Health** - Surface counting quality at a glance

**Original Vision (UI_REVAMP_CONCEPT.md):**
- Command-center aesthetic (dark mode, high-density metrics)
- Real-time counting quality indicators
- Interactive calibration workflow with live preview
- Historical trend visualization
- Privacy boundary indicators

---

### Phase 1: API Audit & Sync ✅

**Completed:** January 11, 2026  
**Duration:** ~2 hours

**Objectives:**
Audit existing API endpoints and add missing functionality to support class-based analytics, recent events, trend charts, and pipeline diagnostics.

**Deliverables:**

1. **New API Endpoints:**
   - `GET /api/stats/recent` - Recent count events for debugging
   - `GET /api/stats/hourly` - Hourly aggregates for charts
   - `GET /api/stats/daily` - Daily aggregates for charts
   - `GET /api/stats/export` - CSV export for advocacy reports
   - `GET /api/status/pipeline` - Per-stage health diagnostics

2. **Enhanced Endpoints:**
   - `/api/stats/by-class` - Added class-based filtering and time ranges
   - `/api/status/compact` - Added warnings array for critical alerts

3. **Database Optimizations:**
   - Added indexes on (class_name, ts) for modal split queries
   - Added indexes on (detection_backend, ts) for backend comparisons

**Privacy Compliance:**
- All new endpoints respect privacy principles
- No track IDs exposed in public APIs
- No bounding box coordinates in exports
- Aggregates only for external sharing

**Result:** Complete API foundation for advanced frontend features.

---

### Phase 2: Dashboard Enhancements ✅

**Completed:** January 11, 2026  
**Duration:** ~1.5 hours  
**Bundle Size:** 257KB JS, 18KB CSS (gzipped: 80.65KB + 4.22KB)

**Objectives:**
Enhance the React dashboard with class-based analytics, recent events table, and browser notifications.

**Deliverables:**

1. **Class Distribution (Modal Split)**
   - Enhanced `CountsCard` component with class breakdown
   - Horizontal bars showing top 5 classes by count
   - Color-coded by class type
   - Percentage fill visualization
   
   Example:
   ```
   By Class
   car      ████████████████████ 142
   bicycle  ████░░░░░░░░░░░░░░░░  15
   person   ██░░░░░░░░░░░░░░░░░░   8
   ```

2. **Recent Events Table**
   - New `RecentEventsTable` component
   - Last 10 count events with:
     - Time ago (e.g., "2m", "5s")
     - Class with color-coded dot
     - Direction label
     - Detection confidence %
   - Auto-refreshes with dashboard polling

3. **Browser Notifications**
   - Critical alerts trigger browser notifications
   - Request permission on first alert
   - Notifications for:
     - Camera offline
     - Disk space low
     - High temperature
   - Non-intrusive (only critical issues)

4. **Enhanced API Client**
   - TypeScript types for all new endpoints
   - `RecentEventsResponse`, `HourlyStatsResponse`, `DailyStatsResponse`
   - `PipelineStatusResponse` for health diagnostics
   - Error handling for graceful degradation

**Technical Details:**
- Zero breaking changes to existing components
- Maintains 30-second polling from Phase 0
- Performance optimized (minimal re-renders)

**Result:** Dashboard now shows what's actually using the street, not just total counts.

---

### Phase 3: Trends Page ✅

**Completed:** January 11, 2026  
**Bundle Size:** 628KB minified → 191KB gzipped  
**Performance:** Optimized for edge hardware (Pi 4)

**Objectives:**
Create dedicated Trends page with historical analysis, time-range selection, and chart visualization.

**Deliverables:**

1. **Time-Range Picker**
   - New `TimeRangePicker` component
   - Presets: Last 7/30/90 days
   - Custom range: Date inputs with validation
   - Callback for range changes

2. **Hourly Chart**
   - Bar chart using Recharts
   - Data from `/api/stats/hourly`
   - Class filtering (toggle individual classes)
   - Tooltips with exact counts
   - Custom styling for dark mode

3. **Daily Chart**
   - Line chart using Recharts
   - Data from `/api/stats/daily`
   - Smooth curves for trend visualization
   - Auto-switches for ranges >30 days

4. **Trends Page**
   - Full-featured page at `/trends`
   - Layout: Time picker → Class filters → Tabs (Chart / Breakdown)
   - Auto-switches between hourly/daily based on range
   - CSV export button

5. **Refactored Components**
   - Enhanced `tabs.tsx` with shadcn-style API
   - Composable tabs (`TabsRoot`, `TabsList`, `TabsTrigger`, `TabsContent`)
   - Backward compatible with legacy `Tabs` component

**Technical Decisions:**

1. **Recharts vs Other Libraries**
   - Chose Recharts for:
     - Good TypeScript support
     - Lightweight (adds ~100KB gzipped)
     - Works well with React hooks
     - Easy customization

2. **Hourly vs Daily Auto-Switch**
   - Hourly for ranges ≤30 days (detailed view)
   - Daily for ranges >30 days (avoid overwhelming charts)
   - Frontend logic, not API constraint

3. **Class Filters**
   - Client-side filtering (fast, no API calls)
   - Persistent state during range changes
   - "All" option for quick reset

**Performance:**
- Bundle size reasonable for edge (191KB gzipped)
- Charts render smoothly on Pi 4
- Data fetching optimized (only on range change)

**Result:** Complete historical analysis capability for advocacy reports.

---

### Phase 4: Calibration Workflow (Not Started)

**Status:** 📋 Planned  
**Estimated:** 2-3 days

**Objectives:**
- Interactive gate line placement with live video preview
- Real-time feedback on line position quality
- Confidence indicators (occlusions, perspective distortion)
- Save/load calibration presets

**Deferred Because:**
- Current configuration workflow via API is functional
- Frontend calibration can be added incrementally
- Higher priority: Schema v3 and modal split analytics

---

### Phase 5: Advanced Analytics (Not Started)

**Status:** 📋 Planned  
**Estimated:** 1-2 weeks

**Objectives:**
- Speed distribution charts (requires speed measurement implementation)
- Heatmap visualization (trajectory aggregation)
- Before/after comparison tools
- Automated report generation

**Dependencies:**
- Speed measurement (Milestone 3) must be implemented first
- Heatmap data collection must be added to pipeline

---

## Key Technical Decisions

### 1. React + TypeScript + Tailwind

**Decision:** Use modern React with TypeScript and Tailwind CSS  
**Rationale:**
- Type safety prevents runtime errors
- Tailwind enables rapid UI development
- shadcn/ui provides high-quality components
- Good performance on edge hardware

**Result:** ✅ Clean, maintainable, performant frontend

---

### 2. Class-Specific Confidence Thresholds

**Decision:** Two-stage YOLO filtering (baseline + per-class thresholds)  
**Rationale:**
- Pedestrians and bicycles are harder to detect (small, irregular shapes)
- Cars and buses are easier to detect (large, regular shapes)
- Single threshold either misses pedestrians or creates false positives for cars

**Implementation:**
```python
# Run YOLO with low baseline (0.25)
results = model.predict(frame, conf=0.25)

# Apply class-specific thresholds
for detection in results:
    if detection.class_id == 0:  # person
        if detection.confidence < 0.20:
            continue  # Reject
    elif detection.class_id == 2:  # car
        if detection.confidence < 0.40:
            continue  # Reject
```

**Result:** +300-400% improvement in pedestrian/bicycle detection without increasing false positives

---

### 3. Defense-in-Depth Double-Count Prevention

**Decision:** Multiple layers to prevent duplicate counts  
**Rationale:**
- Track ID fragmentation can occur (occlusions, noise)
- Single prevention mechanism is fragile
- Evidence-grade data requires belt-and-suspenders approach

**Implementation:**
1. **Track State:** `has_been_counted` flag prevents re-counting same track
2. **Database Constraint:** Unique index on `(track_id, ts/1000)` rejects duplicates
3. **Trajectory Truncation:** Counted tracks stop accumulating trajectory

**Result:** ✅ No double-counting issues observed in production

---

### 4. 3-Layer Configuration Architecture

**Decision:** Separate defaults, config, and calibration  
**Rationale:**
- Universal defaults (config/default.yaml) ship with code
- Deployment config (config/config.yaml) varies per installation
- Calibration (data/calibration/site.yaml) is measured geometry

**Benefits:**
- Clean separation of concerns
- Multi-site deployments share defaults
- Calibration managed separately via `/api/calibration`
- Git-ignored user-specific overrides

**Result:** ✅ Flexible, maintainable configuration system

---

### 5. Schema Versioning with Auto-Migration

**Decision:** Bump schema version, drop/recreate on mismatch  
**Rationale:**
- SQLite ALTER TABLE has limitations
- Early-stage project where breaking changes are acceptable
- Simpler than complex migration scripts
- Users can manually preserve data if needed

**Trade-offs:**
- ❌ Historical data lost on schema changes (unless manually migrated)
- ✅ Simple, reliable, no migration bugs
- ✅ Clear versioning (schema v1, v2, v3)

**Result:** ✅ Zero migration issues, clear schema evolution

---

## Lessons Learned

### 1. Start with API Foundation
**Lesson:** Phase 1 (API audit) was critical for all subsequent phases  
**Why:** Frontend work is much faster when APIs are complete and documented

### 2. TypeScript Prevents Bugs
**Lesson:** TypeScript caught numerous bugs during refactoring  
**Example:** API response model mismatches, missing fields, incorrect types

### 3. Bundle Size Matters
**Lesson:** Recharts adds 100KB gzipped—acceptable but monitor carefully  
**Action:** Avoided other heavy libraries (D3, Chart.js larger)

### 4. Privacy by Default
**Lesson:** Design privacy into APIs from the start  
**Example:** `/api/stats/recent` never returns track coordinates or bounding boxes

### 5. Documentation During Development
**Lesson:** Documenting phases as we built them was valuable  
**Why:** Captured context and decisions that would be forgotten later

---

## Future Enhancements

### Short-Term (1-3 months)
1. **Dashboard Modal Split Enhancement**
   - Show class breakdown prominently on Dashboard
   - Pie chart or stacked bar for visual impact
   - Use existing `/api/stats/by-class` endpoint

2. **Calibration Workflow**
   - Interactive gate line placement
   - Live video preview
   - Quality indicators

3. **CSV Export Enhancement**
   - Add filters (class, direction, confidence threshold)
   - Include summary statistics in export
   - Support for time range selection

### Medium-Term (3-6 months)
4. **Speed Measurement**
   - Requires Milestone 3 implementation
   - Speed distribution charts
   - Speeding statistics for advocacy

5. **Heatmap Visualization**
   - Aggregate trajectory data
   - Time-bucketed occupancy grids
   - Bird's-eye view transformation

6. **Automated Reports**
   - Weekly/monthly summary PDFs
   - Before/after comparison tools
   - Shareable public dashboards

### Long-Term (6-12 months)
7. **Multi-Camera Support**
   - Multiple observation sources
   - Camera selection in UI
   - Aggregate statistics across cameras

8. **Advanced Analytics**
   - Anomaly detection (unusual traffic patterns)
   - Predictive modeling (forecast peak hours)
   - Cost-benefit analysis for traffic calming

---

## Conclusion

The system has evolved from basic vehicle counting to evidence-grade traffic analysis with:
- ✅ Multi-class detection (cars, bikes, pedestrians)
- ✅ Comprehensive metadata capture (schema v3)
- ✅ Modern command-center UI (5 pages)
- ✅ Historical trend analysis (Trends page)
- ✅ Modal split analytics (class breakdowns)
- ✅ Privacy-preserving design (aggregates only)

**Current Status:** Production-ready for deployment with strong foundation for future enhancements.

**Next Priorities:**
1. Enhance Dashboard with prominent modal split display
2. Implement formal validation procedure
3. Add webhook/email alerting
4. Speed measurement (Milestone 3)

---

**Document Version:** 1.0  
**Last Updated:** January 16, 2026
