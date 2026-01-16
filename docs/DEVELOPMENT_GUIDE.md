# Development Guide

**Target Audience:** Developers contributing to the Traffic Monitoring System  
**Last Updated:** January 16, 2026

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Development Workflow](#development-workflow)
4. [Adding Features](#adding-features)
5. [Testing](#testing)
6. [Debugging](#debugging)
7. [Common Tasks](#common-tasks)

---

## Quick Start

### Prerequisites

- **Python 3.9+** (3.11+ recommended)
- **Node.js 18+** and npm
- **Git**
- **Optional:** GPU with CUDA for YOLO development

### Initial Setup

```bash
# 1. Clone repository
git clone https://github.com/your-username/traffic-monitor.git
cd traffic-monitor

# 2. Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install YOLO (optional, for multi-class detection)
pip install ultralytics

# 5. Build frontend
cd frontend
npm install
npm run build
cd ..

# 6. Run tests
pytest tests/ -v

# 7. Start development server
python src/main.py --config config/default.yaml --display
```

### Verify Installation

Open browser to `http://localhost:5000` - you should see the dashboard.

---

## Architecture Overview

### Layer Responsibilities

```
┌──────────────────────────────────────────────────┐
│ OBSERVATION: Frame capture and transforms       │
│ → OpenCVSource, Picamera2Source                 │
└──────────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────┐
│ DETECTION: Object detection                      │
│ → BgSubDetector, UltralyticsYoloDetector        │
└──────────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────┐
│ TRACKING: Multi-object tracking                  │
│ → IoUTracker (src/tracking/tracker.py)          │
└──────────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────┐
│ COUNTING: Gate/Line crossing logic               │
│ → GateCounter, LineCounter                      │
└──────────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────┐
│ STORAGE: SQLite persistence (schema v3)          │
│ → Database (src/storage/database.py)            │
└──────────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────┐
│ WEB: FastAPI + React UI                          │
│ → API routes, frontend pages                    │
└──────────────────────────────────────────────────┘
```

### Key Principles

1. **Strict layer boundaries** - Data flows one direction: observation → storage
2. **Pluggable backends** - Detection, inference, camera sources are swappable
3. **Edge-first** - Must work without internet
4. **Defense-in-depth** - Multiple mechanisms prevent double-counting
5. **Schema versioning** - Database schema is versioned and migrated

See `docs/architect_constitution.md` for complete design principles.

---

## Development Workflow

### Git Workflow

```bash
# 1. Create feature branch
git checkout -b feature/your-feature-name

# 2. Make changes
# ... edit code ...

# 3. Run tests
pytest tests/ -v

# 4. Commit (use conventional commits)
git add .
git commit -m "feat: add feature description"

# 5. Push and create PR
git push origin feature/your-feature-name
```

### Conventional Commit Messages

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring (no behavior change)
- `test:` Adding/updating tests
- `chore:` Maintenance tasks

### Running in Development Mode

**Backend only:**
```bash
python src/main.py --config config/default.yaml --display
```

**Frontend only (hot reload):**
```bash
cd frontend
npm run dev
# Access at http://localhost:5173 (proxies API to :5000)
```

**Both (for full-stack development):**
```bash
# Terminal 1: Backend
python src/main.py --config config/default.yaml

# Terminal 2: Frontend
cd frontend && npm run dev
```

### Code Style

**Python:**
- Follow PEP 8
- Use type hints where possible
- Maximum line length: 100 characters
- Use dataclasses for data structures

**TypeScript:**
- Use ESLint rules (configured in frontend)
- Prefer functional components
- Use TypeScript strict mode
- Export types alongside components

---

## Adding Features

### Where Does New Code Go?

**Question:** I want to add a new detection backend

**Answer:** 
1. Create `src/detection/your_detector.py`
2. Inherit from `Detector` base class
3. Implement `detect(frame) -> List[Detection]`
4. Add configuration to `config/default.yaml`
5. Update `src/detection/init.py` factory function

**Example:**
```python
# src/detection/your_detector.py
from .base import Detector, Detection
from typing import List
import numpy as np

class YourDetector(Detector):
    def __init__(self, config):
        self.config = config
        # Initialize your detector
        
    def detect(self, frame: np.ndarray) -> List[Detection]:
        # Your detection logic here
        detections = []
        # ... process frame ...
        return detections
```

---

**Question:** I want to add a new API endpoint

**Answer:**
1. Add route to `src/web/routes/api.py`
2. Create Pydantic model in `src/web/api_models.py` (if needed)
3. Add service logic to `src/web/services/` (if complex)
4. Update frontend API client (`frontend/src/lib/api.ts`)
5. Add TypeScript types for response

**Example:**
```python
# src/web/routes/api.py
@router.get("/your-endpoint")
def your_endpoint(param: str = None):
    # Your logic here
    return {"result": "data"}
```

---

**Question:** I want to add a new frontend page

**Answer:**
1. Create `frontend/src/pages/YourPage.tsx`
2. Add route to `frontend/src/App.tsx`
3. Add navigation link in `frontend/src/components/Layout.tsx`
4. Create supporting components in `frontend/src/components/`

**Example:**
```tsx
// frontend/src/pages/YourPage.tsx
export function YourPage() {
  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold">Your Page</h1>
      {/* Your content */}
    </div>
  );
}
```

---

**Question:** I want to add a new counting strategy

**Answer:**
1. Create `src/algorithms/counting/your_counter.py`
2. Inherit from `Counter` base class
3. Implement `process_tracks(tracks) -> List[CountEvent]`
4. Add configuration to `config/default.yaml`
5. Update counter factory in `src/algorithms/counting/__init__.py`

**Example:**
```python
# src/algorithms/counting/your_counter.py
from .base import Counter, CountEvent
from typing import List
from models.track import Track

class YourCounter(Counter):
    def process_tracks(self, tracks: List[Track]) -> List[CountEvent]:
        events = []
        # Your counting logic
        return events
```

---

### Testing Requirements

**All new features must include:**
1. Unit tests for core logic
2. Integration test if touching multiple layers
3. Type hints for Python code
4. TypeScript types for frontend code

**Test file naming:**
```
tests/test_your_feature.py      # Python tests
frontend/src/tests/*.test.tsx   # Frontend tests (if added)
```

---

## Testing

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_counting.py -v

# Specific test function
pytest tests/test_counting.py::test_gate_counter_basic -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### Writing Tests

**Example: Testing a counting strategy**
```python
# tests/test_your_counter.py
import pytest
from src.algorithms.counting.your_counter import YourCounter
from src.models.track import Track

def test_your_counter_basic():
    counter = YourCounter(config={})
    
    # Create test tracks
    tracks = [
        Track(id=1, bbox=[100, 100, 150, 150], trajectory=[[100, 100], [120, 100]]),
    ]
    
    # Process tracks
    events = counter.process_tracks(tracks)
    
    # Assert expected behavior
    assert len(events) == 1
    assert events[0].direction == "A_TO_B"
```

### Test Data

**Use fixtures for complex setup:**
```python
@pytest.fixture
def sample_tracks():
    return [
        Track(id=1, bbox=[...], trajectory=[...]),
        Track(id=2, bbox=[...], trajectory=[...]),
    ]

def test_with_fixture(sample_tracks):
    counter = YourCounter()
    events = counter.process_tracks(sample_tracks)
    assert len(events) == 2
```

---

## Debugging

### Logging

The system uses Python's `logging` module. Logs are written to:
- **Console**: INFO and above
- **File**: `logs/traffic_monitor.log` (DEBUG and above)

**Add logging to your code:**
```python
import logging

logger = logging.getLogger(__name__)

def your_function():
    logger.debug("Detailed information")
    logger.info("General information")
    logger.warning("Warning message")
    logger.error("Error occurred")
```

### Health Endpoints

**Check system health:**
```bash
curl http://localhost:5000/api/health
curl http://localhost:5000/api/status
curl http://localhost:5000/api/status/pipeline
```

### Common Issues

**Issue: Camera not detected**
```bash
# Check available cameras (Linux)
v4l2-ctl --list-devices

# Test camera directly
python tools/test_camera.py --device-id 0
```

**Issue: YOLO not loading**
```bash
# Verify installation
pip list | grep ultralytics

# Test YOLO directly
python tools/test_yolo_detection.py --model yolov8s.pt
```

**Issue: Database locked**
```bash
# Stop all instances
python src/main.py --stop

# Check PID file
cat data/traffic_monitor.pid

# Remove stale PID file if process is not running
rm data/traffic_monitor.pid
```

**Issue: Frontend not connecting to backend**
```bash
# Check backend is running
curl http://localhost:5000/api/health

# Check frontend proxy configuration
cat frontend/vite.config.ts

# Restart both frontend and backend
```

---

## Common Tasks

### Task: Add a new YOLO class

**1. Update configuration:**
```yaml
# config/default.yaml
detection:
  yolo:
    classes: [0, 1, 2, 3, 5, 7, 8]  # Added 8 (boat)
    class_name_overrides:
      8: "boat"
    class_thresholds:
      8: 0.35  # Medium threshold
```

**2. No code changes needed** - system automatically picks up new class

**3. Verify in database:**
```sql
SELECT class_name, COUNT(*) FROM count_events 
WHERE class_name = 'boat' 
GROUP BY class_name;
```

---

### Task: Add a new API endpoint for statistics

**1. Create endpoint:**
```python
# src/web/routes/api.py
@router.get("/stats/your-stat")
def your_stat(start_ts: Optional[float] = None):
    cfg = ConfigService.load_effective_config()
    db_path = cfg["storage"]["local_database_path"]
    service = StatsService(db_path=db_path)
    return service.get_your_stat(start_ts)
```

**2. Add service method:**
```python
# src/web/services/stats_service.py
def get_your_stat(self, start_ts: Optional[float] = None):
    # Your query logic
    return {"result": data}
```

**3. Update frontend:**
```typescript
// frontend/src/lib/api.ts
export async function getYourStat(startTs?: number) {
  const params = startTs ? `?start_ts=${startTs}` : '';
  const res = await fetch(`/api/stats/your-stat${params}`);
  return await res.json();
}
```

---

### Task: Modify the counting logic

**Warning:** Counting logic changes can affect data quality. Follow these steps carefully.

**1. Create a new counting strategy (recommended) or modify existing one:**
```python
# src/algorithms/counting/your_counter.py
class YourCounter(Counter):
    def process_tracks(self, tracks: List[Track]) -> List[CountEvent]:
        # Your improved counting logic
        pass
```

**2. Add comprehensive tests:**
```python
# tests/test_your_counter.py
def test_edge_case_occlusion():
    # Test behavior with occluded vehicles
    pass

def test_edge_case_uturn():
    # Test behavior with U-turns
    pass
```

**3. Update configuration:**
```yaml
# config/config.yaml
counting:
  mode: "your_counter"  # Switch to your counter
```

**4. Run validation:**
- Compare counts against ground truth for 3× 10-minute windows
- Document accuracy improvements
- Update docs/PLAN.md with validation results

---

### Task: Update the database schema

**Warning:** Schema changes require careful migration planning.

**1. Plan your changes:**
- What fields are you adding/removing?
- Are they nullable (backward compatible)?
- Do you need new indexes?

**2. Bump schema version:**
```python
# src/storage/database.py
EXPECTED_SCHEMA_VERSION = 4  # Increment
```

**3. Update table creation:**
```python
# src/storage/database.py
def _create_schema(self):
    cursor.execute("""
        CREATE TABLE count_events (
            -- ... existing fields ...
            your_new_field TEXT,  -- Add your field
        )
    """)
```

**4. Update data models:**
```python
# src/models/count_event.py
@dataclass
class CountEvent:
    # ... existing fields ...
    your_new_field: Optional[str] = None
```

**5. Document migration:**
- Add migration guide to docs/SCHEMA_V4.md (create new doc)
- Document what changed and why
- Provide rollback procedure

---

## Development Best Practices

### 1. Read the Governance Documents First

Before making changes, read:
- `docs/architect_constitution.md` - Design principles
- `docs/PLAN.md` - Current architecture and roadmap

### 2. Keep Changes Small

- One feature per PR
- Separate refactoring from behavior changes
- Make incremental improvements

### 3. Maintain Layer Boundaries

❌ **Bad:** Accessing database directly from counting logic
```python
# src/algorithms/counting/gate.py
def process_tracks(self, tracks):
    db.execute("INSERT INTO ...") # NO!
```

✅ **Good:** Return CountEvent, let storage layer persist
```python
def process_tracks(self, tracks):
    return [CountEvent(...)]  # YES!
```

### 4. Write Tests for Edge Cases

Focus on:
- Occlusions (track fragmentation)
- U-turns (direction changes)
- Boundary conditions (tracks at frame edges)
- Empty inputs (no detections)

### 5. Document Your Decisions

Add comments explaining **why**, not **what**:

❌ **Bad:**
```python
# Increment counter
counter += 1
```

✅ **Good:**
```python
# Only count if track has crossed both lines (prevents half-crossings)
if track.crossed_line_a and track.crossed_line_b:
    counter += 1
```

---

## Getting Help

### Documentation

- `docs/architect_constitution.md` - Design principles
- `docs/PLAN.md` - Architecture and roadmap
- `docs/SCHEMA_V3.md` - Database schema reference
- `docs/DEPLOYMENT.md` - Deployment guide
- `README.md` - Quick start and overview

### Code Navigation

**Key entry points:**
- `src/main.py` - Application entry point
- `src/pipeline/engine.py` - Main processing loop
- `src/web/app.py` - Web server setup
- `frontend/src/App.tsx` - Frontend entry point

**Key interfaces:**
- `src/detection/base.py` - Detection interface
- `src/algorithms/counting/base.py` - Counter interface
- `src/observation/base.py` - Camera source interface

### Common Commands

```bash
# Run with debug logging
python src/main.py --config config/default.yaml --display --log-level DEBUG

# Run tests with verbose output
pytest tests/ -v -s

# Check database contents
sqlite3 data/database.sqlite "SELECT * FROM count_events LIMIT 10;"

# Rebuild frontend
cd frontend && npm run build

# Format Python code
black src/ tests/

# Type check Python code
mypy src/
```

---

## Contributing

### Pull Request Process

1. **Create feature branch** from `main`
2. **Make changes** following coding standards
3. **Write tests** for new functionality
4. **Run full test suite** and verify all pass
5. **Update documentation** if needed
6. **Create PR** with clear description
7. **Address review feedback**
8. **Squash commits** before merge (if requested)

### Code Review Checklist

- [ ] Tests added for new functionality
- [ ] All tests passing
- [ ] No linter errors
- [ ] Documentation updated
- [ ] Layer boundaries respected
- [ ] Type hints added (Python)
- [ ] TypeScript types defined (frontend)
- [ ] Commit messages follow conventional commits
- [ ] No breaking changes (or clearly documented)

---

## Conclusion

This guide covers the essentials for developing on the Traffic Monitoring System. Remember:

1. **Read the constitution** - `docs/architect_constitution.md`
2. **Respect layer boundaries** - Strict data flow
3. **Test your changes** - Unit tests required
4. **Keep it simple** - Favor simplicity over cleverness
5. **Document decisions** - Explain why, not what

**Welcome to the project! Happy coding! 🚀**

---

**Document Version:** 1.0  
**Last Updated:** January 16, 2026
