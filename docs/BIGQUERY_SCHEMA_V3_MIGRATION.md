# BigQuery Schema v3 Migration

## Overview

Schema v3 adds 6 new columns to the `vehicle_detections` table to support:
- **Modal split analytics** (Milestone 4)
- **Detection quality assessment**
- **Operational debugging**

## New Columns

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| `class_id` | INTEGER | NULLABLE | YOLO class ID (0=person, 2=car, etc.) |
| `class_name` | STRING | NULLABLE | Human-readable class name (car, person, truck, etc.) |
| `confidence` | FLOAT | NULLABLE | Detection confidence score (0.0-1.0) |
| `detection_backend` | STRING | NULLABLE | Detection backend (yolo, bgsub, hailo) |
| `platform` | STRING | NULLABLE | Operating system and version |
| `process_pid` | INTEGER | NULLABLE | Process ID that made the detection |

## Migration Methods

### Method 1: Auto-Migration (Recommended)

**What happens:**
- Next time CloudSync initializes, it automatically detects missing columns
- Adds missing columns to existing tables
- Logs the changes to the application log

**When it runs:**
- On application startup when cloud sync is enabled
- Safe to run multiple times (idempotent)

**What you need to do:**
1. Restart the backend with cloud sync enabled
2. Check logs for migration messages:
   ```
   [INFO] Updating BigQuery table 'vehicle_detections' schema...
   [INFO] Adding 6 missing columns: ['class_id', 'class_name', ...]
   [INFO] Successfully updated BigQuery table 'vehicle_detections' schema
   ```

**Pros:**
- ✅ Fully automatic
- ✅ No manual intervention needed
- ✅ Works for future schema updates

**Cons:**
- ❌ Requires app restart to trigger

---

### Method 2: Manual Migration Script (Backup)

**What it does:**
- Standalone Python script that adds missing columns
- Can run independently of the main application
- Provides dry-run mode to preview changes

**When to use:**
- Auto-migration failed or didn't run
- You want to migrate before restarting the app
- You want to preview changes first

**How to run:**

1. **Preview changes (dry-run):**
   ```bash
   python tools/migrate_bigquery_schema_v3.py --dry-run
   ```

2. **Apply migration:**
   ```bash
   python tools/migrate_bigquery_schema_v3.py
   ```

3. **Custom config file:**
   ```bash
   python tools/migrate_bigquery_schema_v3.py --config path/to/cloud_config.yaml
   ```

**Example output:**
```
============================================================
BigQuery Schema Migration: Schema v3
============================================================
[INFO] Loading configuration from config/cloud_config.yaml
[INFO] Initializing BigQuery client
[INFO] ✅ Connected to project: traffic-monitor-123456
[INFO] Target table: traffic-monitor-123456.traffic_data.vehicle_detections
[INFO] Checking current table schema...
[INFO] ✅ Table exists with 7 columns
============================================================
UPDATING TABLE SCHEMA
============================================================
[INFO] 📊 Adding 6 missing columns:
[INFO]    - class_id (INTEGER, NULLABLE): YOLO class ID
[INFO]    - class_name (STRING, NULLABLE): Human-readable class name
[INFO]    - confidence (FLOAT, NULLABLE): Detection confidence score (0.0-1.0)
[INFO]    - detection_backend (STRING, NULLABLE): Detection backend (yolo, bgsub, hailo)
[INFO]    - platform (STRING, NULLABLE): Operating system and version
[INFO]    - process_pid (INTEGER, NULLABLE): Process ID that made the detection
[INFO] ✅ Successfully updated table schema
============================================================
[INFO] ✅ Migration completed successfully
[INFO] 💡 New data will now include schema v3 fields
```

**Pros:**
- ✅ Full control over timing
- ✅ Dry-run mode for safety
- ✅ Works independently

**Cons:**
- ❌ Requires manual execution

---

## Important Notes

### Data Safety

✅ **Safe operations:**
- Only adds new columns (never drops or modifies)
- Existing data is preserved
- Existing rows will have NULL for new columns (expected)
- Operation is idempotent (can run multiple times safely)

❌ **Not destructive:**
- Does NOT drop columns
- Does NOT modify data types
- Does NOT delete data

### Permissions Required

You need `bigquery.tables.update` permission on the target dataset.

To check your permissions:
```bash
gcloud projects get-iam-policy YOUR-PROJECT-ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:YOUR-EMAIL"
```

### Cost

- ALTER TABLE operations are **free** in BigQuery
- Syncing more columns will increase storage costs (minimal)
- Query costs depend on which columns you SELECT

### Backward Compatibility

- Old data: Rows created before migration will have NULL for new columns
- New data: Rows created after migration will have populated values
- Queries: Both old and new rows can be queried together

---

## Verification

After migration, verify the schema was updated:

### Option 1: Check in BigQuery Console

1. Go to [BigQuery Console](https://console.cloud.google.com/bigquery)
2. Navigate to your dataset → `vehicle_detections` table
3. Click "Schema" tab
4. Verify 6 new columns are present

### Option 2: Query the Schema

```sql
SELECT column_name, data_type, is_nullable
FROM `your-project.dataset.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'vehicle_detections'
AND column_name IN (
  'class_id', 'class_name', 'confidence',
  'detection_backend', 'platform', 'process_pid'
)
ORDER BY ordinal_position;
```

### Option 3: Check Application Logs

Look for these log messages:
```
[INFO] BigQuery table 'vehicle_detections' exists
[INFO] Updating BigQuery table 'vehicle_detections' schema...
[INFO] Adding 6 missing columns: ['class_id', 'class_name', ...]
[INFO] Successfully updated BigQuery table 'vehicle_detections' schema
```

Or if already up to date:
```
[INFO] BigQuery table 'vehicle_detections' schema is up to date
```

---

## Troubleshooting

### "Permission denied" error

**Problem:** You don't have `bigquery.tables.update` permission

**Solutions:**
1. Ask your GCP admin to grant `roles/bigquery.dataEditor` role
2. Or use the manual script from an account with permissions
3. Or manually run ALTER TABLE commands in BigQuery console

### Migration didn't run

**Problem:** Auto-migration didn't execute

**Possible causes:**
- Cloud sync is disabled in config
- Application didn't restart after code update
- Error occurred before sync initialization

**Solutions:**
1. Check `config/cloud_config.yaml` - ensure `enabled: true`
2. Restart the application
3. Run manual migration script as backup

### "Table not found" error

**Problem:** The `vehicle_detections` table doesn't exist yet

**Solution:**
- This is normal for new installations
- Table will be created automatically when CloudSync first runs
- Table will be created with schema v3 from the start

---

## Rollback

If you need to remove the new columns (not recommended):

```sql
ALTER TABLE `your-project.dataset.vehicle_detections`
DROP COLUMN IF EXISTS class_id,
DROP COLUMN IF EXISTS class_name,
DROP COLUMN IF EXISTS confidence,
DROP COLUMN IF EXISTS detection_backend,
DROP COLUMN IF EXISTS platform,
DROP COLUMN IF EXISTS process_pid;
```

⚠️ **Warning:** This will permanently delete data in these columns.

---

## Next Steps

After successful migration:

1. ✅ Verify new columns exist in BigQuery
2. ✅ Confirm new data is being synced with populated values
3. ✅ Update any existing queries/dashboards to use new columns
4. ✅ Begin using schema v3 data for analytics

### Example Queries Using Schema v3

**Modal split analysis:**
```sql
SELECT 
  class_name,
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM `your-project.dataset.vehicle_detections`
WHERE class_name IS NOT NULL
GROUP BY class_name
ORDER BY count DESC;
```

**Detection quality assessment:**
```sql
SELECT 
  detection_backend,
  AVG(confidence) as avg_confidence,
  MIN(confidence) as min_confidence,
  MAX(confidence) as max_confidence,
  COUNT(*) as detections
FROM `your-project.dataset.vehicle_detections`
WHERE confidence IS NOT NULL
GROUP BY detection_backend;
```

**Platform debugging:**
```sql
SELECT 
  platform,
  process_pid,
  detection_backend,
  COUNT(*) as detections
FROM `your-project.dataset.vehicle_detections`
WHERE timestamp >= UNIX_SECONDS(TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR))
GROUP BY platform, process_pid, detection_backend
ORDER BY detections DESC;
```

