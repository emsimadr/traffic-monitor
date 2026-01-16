# 🔄 Restart Backend to Apply Fix

## What Was Fixed

Platform metadata (`detection_backend`, `platform`, `process_pid`) wasn't being captured because the counter was created after the metadata capture call. 

**Fix:** Now the metadata is passed to the MeasureStage and set on the counter when it's created.

## How to Restart

### Option 1: Quick Restart (Recommended)

1. **Find the Backend terminal window** (shows logs like `[COUNT] track_id=...`)
2. Press `Ctrl+C` to stop it
3. Press the UP arrow key to get the last command
4. Press `Enter` to restart

### Option 2: Use Script

```powershell
.\stop-dev.ps1
.\start-dev.ps1
```

### Option 3: Manual Restart

In the backend terminal:
```powershell
python src/main.py --config config/config.yaml --kill-existing
```

## After Restart

Wait 2-3 minutes for some detections, then run:

```powershell
python check_simple.py
```

**Expected Output (Fixed):**
```
Schema Version: 3
Total Events: X

Recent Events:
Track | Direction | Class      | Conf | Backend
-------------------------------------------------------
XX    | A_TO_B    | car        | 0.89 | yolo       ← Should be "yolo" not "unknown"
XX    | B_TO_A    | person     | 0.76 | yolo       ← Should be "yolo" not "unknown"

Platform Metadata:
  Platform: Windows-11-10.0.26200-SP0    ← Should have value, not None
  Process PID: 12345                      ← Should have number, not None  
  Backend: yolo                           ← Should be "yolo" not "unknown"
```

## Verification Checklist

After restart and 2-3 minutes:

- [ ] `detection_backend` shows "yolo" (not "unknown")
- [ ] `platform` shows "Windows-11-..." (not None)
- [ ] `process_pid` shows a number (not None)
- [ ] `class_name` still captured ("car", "person", etc.)
- [ ] `confidence` still captured (0.35-1.0)

✅ = Schema v3 fully working!

