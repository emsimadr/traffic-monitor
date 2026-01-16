"""Quick script to check schema v3 data capture."""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/database.sqlite')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 60)
print("SCHEMA V3 DATA CHECK")
print("=" * 60)

# Check schema version
cursor.execute("SELECT schema_version, created_at FROM schema_meta")
row = cursor.fetchone()
print(f"\n✅ Schema Version: {row['schema_version']}")
print(f"   Created: {row['created_at']}")

# Check total events
cursor.execute("SELECT COUNT(*) as count FROM count_events")
total = cursor.fetchone()['count']
print(f"\n📊 Total Events: {total}")

if total == 0:
    print("\n⚠️  No events yet. System needs to detect and count some objects.")
    print("   Wait a few minutes if you have a camera/video source.")
    conn.close()
    exit(0)

# Check recent events
print("\n📝 Recent Events (last 10):")
cursor.execute("""
    SELECT 
        track_id,
        direction_code,
        class_name,
        confidence,
        detection_backend,
        platform,
        datetime(ts/1000, 'unixepoch', 'localtime') as time
    FROM count_events 
    ORDER BY ts DESC 
    LIMIT 10
""")

print(f"{'Track':<8} {'Direction':<10} {'Class':<12} {'Conf':<6} {'Backend':<8} {'Time'}")
print("-" * 75)
for row in cursor.fetchall():
    class_name = row['class_name'] or 'NULL'
    conf = f"{row['confidence']:.2f}" if row['confidence'] else 'N/A'
    backend = row['detection_backend'] or 'unknown'
    time = row['time']
    print(f"{row['track_id']:<8} {row['direction_code']:<10} {class_name:<12} {conf:<6} {backend:<8} {time}")

# Check class breakdown
print("\n🎯 Class Breakdown:")
cursor.execute("""
    SELECT 
        COALESCE(class_name, 'NULL') as class_name,
        COUNT(*) as count,
        ROUND(AVG(confidence), 3) as avg_conf
    FROM count_events
    GROUP BY class_name
    ORDER BY count DESC
""")

print(f"{'Class':<15} {'Count':<8} {'Avg Confidence'}")
print("-" * 40)
for row in cursor.fetchall():
    print(f"{row['class_name']:<15} {row['count']:<8} {row['avg_conf']:.3f}")

# Check detection backend
print("\n🔧 Detection Backend:")
cursor.execute("""
    SELECT 
        detection_backend,
        COUNT(*) as count
    FROM count_events
    GROUP BY detection_backend
""")

for row in cursor.fetchall():
    print(f"   {row['detection_backend']}: {row['count']} events")

# Check platform metadata
print("\n💻 Platform Metadata:")
cursor.execute("""
    SELECT DISTINCT 
        platform,
        process_pid
    FROM count_events
    WHERE platform IS NOT NULL
    LIMIT 1
""")

row = cursor.fetchone()
if row:
    print(f"   Platform: {row['platform']}")
    print(f"   Process PID: {row['process_pid']}")
else:
    print("   No platform metadata captured yet")

print("\n" + "=" * 60)
print("✅ Schema v3 data check complete!")
print("=" * 60)

conn.close()

