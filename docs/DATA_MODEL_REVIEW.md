# Data Model & BigQuery Structure Review

**Date:** January 11, 2026  
**Reviewer:** AI Assistant  
**Status:** Recommendations for Enhancement

---

## Executive Summary

The current data model is **functional and well-architected** for basic vehicle counting with direction tracking. However, several valuable data points are being **lost in the pipeline** that would support:

1. **Modal split analytics** (Milestone 4: pedestrians vs cyclists vs vehicles)
2. **Validation and accuracy assessment** (detection confidence)
3. **Debugging and operational monitoring** (platform/backend metadata)

### Key Findings

✅ **Working Well:**
- Single canonical table (`count_events`) with clean schema
- Defense-in-depth duplicate prevention via unique constraint
- Proper schema versioning (v2)
- Direction tracking (A_TO_B/B_TO_A) with human-readable labels
- Track metadata (age, displacement) for quality assessment

❌ **Missing Data:**
1. **Detection confidence** - YOLO provides 0-1 confidence scores, but not stored
2. **Object class** - YOLO detects person/bicycle/car/etc., but not stored  
3. **Platform/backend metadata** - No tracking of which detector/process generated the event
4. **Device/deployment info** - No identification of which monitoring station generated data

---

## Current Data Flow

### Detection → Storage Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│ 1. DETECTION                                                  │
│    YoloDetector.detect() → List[Detection]                   │
│    - bbox (x1, y1, x2, y2)                                   │
│    - confidence: float  ✓ (YOLO: 0-1, BgSub: 1.0)            │
│    - class_id: int      ✓ (YOLO: 0-7, BgSub: None)           │
│    - class_name: str    ✓ (YOLO: "car", BgSub: None)         │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 2. CONVERSION (engine.py:207-211)                            │
│    Detection → numpy array [x1, y1, x2, y2]                  │
│    ⚠️  LOSS: confidence, class_id, class_name dropped        │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 3. TRACKING                                                   │
│    VehicleTracker.update(det_array) → TrackedVehicle         │
│    - Only bbox + trajectory available                        │
│    - No confidence or class information                      │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 4. COUNTING                                                   │
│    GateCounter.process() → CountEvent                        │
│    - track_id, direction, timestamps                         │
│    - No confidence or class                                  │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 5. STORAGE                                                    │
│    Database.add_count_event() → SQLite                       │
│    BigQuery sync → vehicle_detections table                  │
└──────────────────────────────────────────────────────────────┘
```

**Root Cause:** The conversion at step 2 (engine.py lines 207-211) discards detection metadata by converting to plain bbox arrays.

---

## Current Schema

### SQLite: `count_events`

```sql
CREATE TABLE count_events (
    id INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL,                 -- epoch milliseconds
    frame_idx INTEGER,
    track_id INTEGER NOT NULL,
    direction_code TEXT NOT NULL,        -- "A_TO_B" or "B_TO_A"
    direction_label TEXT,                -- "northbound" / "southbound"
    gate_sequence TEXT,                  -- "A,B" or "B,A"
    line_a_cross_frame INTEGER,
    line_b_cross_frame INTEGER,
    track_age_frames INTEGER,
    track_displacement_px REAL,
    cloud_synced INTEGER DEFAULT 0,
    
    -- Unique constraint (defense-in-depth duplicate prevention)
    UNIQUE(track_id, ts / 1000)
);
```

### BigQuery: `vehicle_detections`

```sql
CREATE TABLE vehicle_detections (
    id INTEGER REQUIRED,
    timestamp FLOAT REQUIRED,
    date_time STRING REQUIRED,
    direction STRING NULLABLE,
    direction_label STRING NULLABLE,
    recorded_at TIMESTAMP NULLABLE
);
```

---

## Recommendations

### Priority 1: Add Object Classification (Required for Milestone 4)

**Why:** Milestone 4 (Modal Split Analytics) explicitly requires class-specific counting to distinguish vehicles vs pedestrians vs cyclists.

**Implementation:**

1. **Update CountEvent model** (`src/models/count_event.py`):
```python
@dataclass(frozen=True)
class CountEvent:
    track_id: int
    direction: str
    direction_label: str
    timestamp: float
    counting_mode: str = "gate"
    
    # NEW FIELDS
    class_id: Optional[int] = None           # COCO class ID (0-7)
    class_name: Optional[str] = None         # "person", "car", etc.
    
    # Existing fields...
    gate_sequence: Optional[str] = None
    line_a_cross_frame: Optional[int] = None
    line_b_cross_frame: Optional[int] = None
    track_age_frames: int = 0
    track_displacement_px: float = 0.0
```

2. **Update SQLite schema** (bump to v3):
```sql
ALTER TABLE count_events ADD COLUMN class_id INTEGER;
ALTER TABLE count_events ADD COLUMN class_name TEXT;
CREATE INDEX idx_count_events_class ON count_events(class_name);
```

3. **Update BigQuery schema**:
```sql
ALTER TABLE vehicle_detections
ADD COLUMN class_id INTEGER,
ADD COLUMN class_name STRING;
```

4. **Modify pipeline** to preserve class info:
   - Update `Track` model to store `class_id`, `class_name`
   - Pass detection metadata through tracker
   - Include in CountEvent creation

**Benefits:**
- Enable modal split reports (% cars vs bikes vs pedestrians)
- Filter counts by class (e.g., "vulnerable road users only")
- Support privacy goals (count person crossings without storing video)

---

### Priority 2: Add Detection Confidence (Quality Assessment)

**Why:** Required for validation, accuracy assessment, and filtering low-confidence detections.

**Implementation:**

1. **Update CountEvent model**:
```python
@dataclass(frozen=True)
class CountEvent:
    # ... existing fields ...
    
    # NEW FIELD
    confidence: float = 1.0  # Detection confidence (0-1), 1.0 for BgSub
```

2. **Update database schemas** (SQLite + BigQuery):
```sql
ALTER TABLE count_events ADD COLUMN confidence REAL DEFAULT 1.0;
ALTER TABLE vehicle_detections ADD COLUMN confidence FLOAT;
```

3. **Use in validation**:
   - Filter validation reports by confidence threshold
   - Analyze false positive/negative rates by confidence band
   - Identify optimal confidence threshold per deployment

**Benefits:**
- **Validation**: Compare accuracy across confidence thresholds
- **Quality control**: Alert when average confidence drops (camera issue?)
- **Research**: Quantify detection uncertainty in reports

---

### Priority 3: Add Platform/Backend Metadata (Operational)

**Why:** Your observation about duplicate detections from multiple backends is important. Tracking which backend/process created each event helps with:
- Debugging duplicate counts
- Performance comparison (BgSub vs YOLO vs Hailo)
- Audit trail for data quality

**Implementation:**

1. **Update CountEvent model**:
```python
import platform
import os

@dataclass(frozen=True)
class CountEvent:
    # ... existing fields ...
    
    # NEW FIELDS
    detection_backend: str = "unknown"       # "bgsub", "yolo", "hailo"
    platform: Optional[str] = None           # "Windows-10", "Linux-6.1.21-rpi"
    process_pid: Optional[int] = None        # Process ID that created event
```

2. **Capture at pipeline initialization**:
```python
# In RuntimeContext or PipelineEngine
self.metadata = {
    "detection_backend": config["detection"]["backend"],
    "platform": platform.platform(),
    "process_pid": os.getpid(),
}
```

3. **Update database schemas**:
```sql
ALTER TABLE count_events 
ADD COLUMN detection_backend TEXT DEFAULT 'unknown',
ADD COLUMN platform TEXT,
ADD COLUMN process_pid INTEGER;

-- Index for backend comparison queries
CREATE INDEX idx_count_events_backend ON count_events(detection_backend);
```

**Benefits:**
- **Debug duplicates**: Identify if multiple processes are counting same objects
- **Performance analysis**: Compare count rates across backends
- **Audit trail**: Know which system version generated historical data

---

### Priority 4: Add Device/Deployment ID (Multi-Camera Future)

**Why:** Future-proofs for multiple monitoring stations (Open Question in PLAN.md: "Multi-camera: support for multiple observation sources?")

**Implementation:**

1. **Add to config**:
```yaml
# config/config.yaml
deployment:
  device_id: "oak-street-north"  # Unique identifier for this monitoring station
  location: "Oak St & Main St, North-facing"
```

2. **Update CountEvent model**:
```python
@dataclass(frozen=True)
class CountEvent:
    # ... existing fields ...
    
    device_id: Optional[str] = None  # Monitoring station identifier
```

3. **Update schemas**:
```sql
ALTER TABLE count_events ADD COLUMN device_id TEXT;
ALTER TABLE vehicle_detections ADD COLUMN device_id STRING;
CREATE INDEX idx_count_events_device ON count_events(device_id);
```

**Benefits:**
- Support multiple cameras in BigQuery
- Compare traffic patterns across intersections
- Aggregate data from distributed monitoring network

---

## Recommended Schema v3

### Complete `count_events` Table (SQLite)

```sql
CREATE TABLE count_events (
    -- Core identification
    id INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL,
    frame_idx INTEGER,
    track_id INTEGER NOT NULL,
    
    -- Direction tracking
    direction_code TEXT NOT NULL,
    direction_label TEXT,
    gate_sequence TEXT,
    line_a_cross_frame INTEGER,
    line_b_cross_frame INTEGER,
    
    -- Track quality metrics (existing)
    track_age_frames INTEGER,
    track_displacement_px REAL,
    
    -- NEW: Object classification (Priority 1)
    class_id INTEGER,
    class_name TEXT,
    
    -- NEW: Detection quality (Priority 2)
    confidence REAL DEFAULT 1.0,
    
    -- NEW: Platform metadata (Priority 3)
    detection_backend TEXT DEFAULT 'unknown',
    platform TEXT,
    process_pid INTEGER,
    
    -- NEW: Device identification (Priority 4)
    device_id TEXT,
    
    -- Cloud sync
    cloud_synced INTEGER DEFAULT 0
);

-- Indexes
CREATE INDEX idx_count_events_ts ON count_events(ts);
CREATE INDEX idx_count_events_direction ON count_events(direction_code);
CREATE INDEX idx_count_events_cloud_synced ON count_events(cloud_synced);
CREATE INDEX idx_count_events_class ON count_events(class_name);
CREATE INDEX idx_count_events_backend ON count_events(detection_backend);
CREATE INDEX idx_count_events_device ON count_events(device_id);

-- Unique constraint (defense-in-depth)
CREATE UNIQUE INDEX idx_count_events_track_second 
ON count_events(track_id, ts / 1000);
```

### Complete BigQuery `vehicle_detections` Table

```sql
CREATE TABLE vehicle_detections (
    -- Core fields (existing)
    id INTEGER NOT NULL,
    timestamp FLOAT NOT NULL,
    date_time STRING NOT NULL,
    direction STRING,
    direction_label STRING,
    recorded_at TIMESTAMP,
    
    -- NEW: Classification
    class_id INTEGER,
    class_name STRING,
    
    -- NEW: Quality
    confidence FLOAT,
    
    -- NEW: Metadata
    detection_backend STRING,
    platform STRING,
    device_id STRING
)
PARTITION BY DATE(TIMESTAMP_SECONDS(CAST(timestamp AS INT64)))
CLUSTER BY class_name, direction, device_id;
```

**Partitioning Strategy:** Daily partitions by timestamp enable cost-effective queries and automatic expiration.

**Clustering:** Groups by `class_name` (modal split queries), `direction` (directional stats), `device_id` (multi-camera queries).

---

## Migration Strategy

### Phase 1: Immediate (Schema v3)

1. **Bump schema version** to 3 in `src/storage/database.py`
2. **Add new columns** with defaults (won't break existing code)
3. **Update `CountEvent` model** with new optional fields
4. **Test with existing data** (new fields will be NULL/default)

### Phase 2: Pipeline Updates (Week 1)

1. **Modify tracker** to preserve detection metadata
2. **Update `GateCounter`/`LineCounter`** to populate new fields
3. **Capture platform metadata** at engine initialization
4. **Add device_id to config** with sensible default

### Phase 3: BigQuery Migration (Week 2)

1. **Add columns** to BigQuery table (non-breaking)
2. **Update sync logic** to map new fields
3. **Backfill device_id** for existing data (if applicable)

### Phase 4: Utilize New Data (Ongoing)

1. **Add class filter** to dashboard ("Show cars only")
2. **Modal split report** in Health page
3. **Backend comparison** dashboard (if running multiple)
4. **Confidence-based validation** tool

---

## Open Questions

1. **Class filtering at counting stage?**  
   Should the counting logic filter by class (e.g., only count vehicles, not pedestrians)? Or count all and filter in queries?  
   **Recommendation:** Count all, filter in queries (more flexible).

2. **Confidence threshold enforcement?**  
   Should low-confidence detections be excluded from counting?  
   **Recommendation:** Store all counts with confidence, allow post-hoc filtering.

3. **Device ID assignment?**  
   Manual config vs auto-generated (hostname-based)?  
   **Recommendation:** Manual config for clarity, with hostname fallback.

4. **Historical data backfill?**  
   Attempt to infer class/confidence for existing events?  
   **Recommendation:** No backfill. Mark old data with `class_name=NULL`, `detection_backend='legacy'`.

---

## Alignment with Project Goals

### ✅ Supports Documented Milestones

- **Milestone 4 (Modal Split):** Class tracking enables pedestrian/bicycle/vehicle breakdown
- **Milestone 1 (Validation):** Confidence enables accuracy assessment
- **Milestone 6 (Reliability):** Platform metadata helps debug duplicate counts

### ✅ Maintains Privacy-First Approach

- Stores **aggregate classifications** (counts by class), not images
- No personally identifiable information
- Supports advocacy goals (e.g., "X% vulnerable road users") without surveillance

### ✅ Defense-in-Depth Enhanced

Your observation about duplicates from multiple backends is addressed:
- Existing: Unique constraint prevents same track_id in same second
- New: `process_pid` + `detection_backend` help identify and debug multi-process races
- Better solution: Process management (already implemented with PID file)

---

## Conclusion

The current data model is **well-designed for its current scope** (basic counting with direction). To support planned features (modal split, validation, multi-camera), we recommend:

1. **Priority 1:** Add `class_id` and `class_name` (required for Milestone 4)
2. **Priority 2:** Add `confidence` (required for validation)
3. **Priority 3:** Add platform metadata (operational debugging)
4. **Priority 4:** Add `device_id` (future multi-camera support)

All changes are **backward compatible** (new nullable/default columns) and support the project's evidence-based advocacy goals.

**Next Steps:**
1. Review this document with project stakeholders
2. Decide on priorities based on immediate needs
3. Implement schema v3 migration
4. Update pipeline to populate new fields
5. Create validation/modal split reports using new data


