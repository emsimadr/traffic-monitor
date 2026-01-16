import sqlite3

conn = sqlite3.connect('data/database.sqlite')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Schema version
cursor.execute("SELECT schema_version FROM schema_meta")
print(f"Schema Version: {cursor.fetchone()['schema_version']}")

# Total events
cursor.execute("SELECT COUNT(*) as count FROM count_events")
total = cursor.fetchone()['count']
print(f"Total Events: {total}\n")

if total > 0:
    # Recent events
    cursor.execute("""
        SELECT 
            track_id,
            direction_code,
            class_name,
            ROUND(confidence,2) as conf,
            detection_backend
        FROM count_events 
        ORDER BY ts DESC 
        LIMIT 10
    """)
    
    print("Recent Events:")
    print("Track | Direction | Class      | Conf | Backend")
    print("-" * 55)
    for row in cursor.fetchall():
        class_name = row['class_name'] or 'NULL'
        print(f"{row['track_id']:<5} | {row['direction_code']:<9} | {class_name:<10} | {row['conf']:<4} | {row['detection_backend']}")
    
    # Class breakdown
    cursor.execute("""
        SELECT 
            COALESCE(class_name, 'NULL') as cls,
            COUNT(*) as cnt,
            ROUND(AVG(confidence),3) as avg_conf
        FROM count_events
        GROUP BY class_name
        ORDER BY cnt DESC
    """)
    
    print("\nClass Breakdown:")
    print("Class        | Count | Avg Confidence")
    print("-" * 45)
    for row in cursor.fetchall():
        print(f"{row['cls']:<12} | {row['cnt']:<5} | {row['avg_conf']}")
    
    # Platform metadata
    cursor.execute("""
        SELECT DISTINCT platform, process_pid, detection_backend
        FROM count_events
        LIMIT 1
    """)
    row = cursor.fetchone()
    print("\nPlatform Metadata:")
    print(f"  Platform: {row['platform']}")
    print(f"  Process PID: {row['process_pid']}")
    print(f"  Backend: {row['detection_backend']}")

conn.close()
print("\n=== Schema v3 verification complete! ===")

