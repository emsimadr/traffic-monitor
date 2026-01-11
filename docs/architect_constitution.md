# Systems Architect Constitution  
Neighborhood Traffic Monitoring System

This document defines the non-negotiable principles that govern all design and implementation work on this project. Any code, refactor, feature, or architectural change must comply with these rules.

This system exists to produce **credible, privacy-respecting, evidence-grade traffic data** for public interest use.

---

## 1. Privacy is foundational

- The system must never identify people, faces, license plates, or track individuals across days.
- Aggregates and summaries are the product. Raw video is transient and for validation only.
- Defaults must be conservative: short retention, minimal data, explicit opt-ins for anything sensitive.
- No feature may weaken privacy even if it improves accuracy or convenience.

---

## 2. Evidence-grade means reproducible

- Every measurement (counts, direction, speed, heatmaps) must have:
  - A documented method
  - Explicit assumptions
  - A validation or calibration path
- Heuristics are allowed only when they are:
  - Configurable
  - Commented
  - Testable

---

## 3. Edge-first reliability

- The system must run and collect data without internet access.
- Cloud sync is optional, asynchronous, and never blocks counting.
- Failures degrade gracefully: the system stays alive and reports warnings.

---

## 4. Architectural boundaries are real

Each layer has a single responsibility:

- Observation: frame capture and transforms
- Detection: object detection
- Tracking: track identity over time
- Counting: logic for crossings and direction
- Storage: persistence and schema
- Web/API: presentation and control

New logic belongs in the correct layer. No shortcuts.

---

## 5. Small, reviewable changes

- Prefer small, incremental diffs over sweeping rewrites.
- Structural refactors must not mix with behavior changes.
- Every change should be easy to validate and easy to revert.

---

## 6. Configuration is part of the API

- Every tunable parameter must live in YAML with documented defaults.
- Defaults must favor stability and privacy.
- Breaking changes require a schema or config version bump and migration notes.

---

## 7. Data contracts are sacred

- Direction codes (`A_TO_B`, `B_TO_A`) and `CountEvent` fields are canonical.
- Schema changes require:
  - Version bump
  - Migration path
  - Backward compatibility or conversion

---

## 8. Defense in depth for counting

Double counting is the primary failure mode.

The system must use multiple protections:
- Track state
- Counter logic
- Database constraints
- Tests for occlusions, fragmentation, and re-detection

---

## 9. Performance is a budget

- Per-frame work must be lightweight.
- New heavy computation must be optional and measurable.
- The system must remain usable on Raspberry Pi class hardware.

---

## 10. Observability is a feature

The system must make its own health visible:
- Camera failures
- Detector failures
- Dropped frames
- Sync issues
- Disk and temperature limits

These must surface through logs and `/api/status` or `/api/health`.

---

## 11. Develop on powerful hardware, deploy to edge

- New features should be developed and validated on a capable dev machine first
  (GPU workstation, adequate RAM/CPU).
- Only after functionality is proven should the code be tested on edge hardware
  (Raspberry Pi).
- This reduces iteration time and separates "does it work?" from "does it fit?"
- Edge-specific backends (e.g., Hailo) are implemented as swappable alternatives
  to dev backends (e.g., CUDA YOLO), not replacements.
- The same interface must work on both, selectable via configuration.

---

This constitution exists to protect the system from becoming:
- Surveillance
- Fragile
- Over-engineered
- Or untrustworthy

All changes must move the project toward:
**Reliable, privacy-preserving, defensible evidence.**
