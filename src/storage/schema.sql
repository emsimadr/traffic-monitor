-- SQLite schema for traffic monitoring (gate-first, version 1)
-- Matches src/storage/database.py initialize()

-- Schema versioning
CREATE TABLE IF NOT EXISTS schema_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    schema_version INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Count events (gate-first schema)
CREATE TABLE IF NOT EXISTS count_events (
    id INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL,                    -- epoch milliseconds
    frame_idx INTEGER,                      -- frame when counted
    track_id INTEGER NOT NULL,              -- tracker ID
    direction_code TEXT NOT NULL,           -- 'A_TO_B' or 'B_TO_A'
    direction_label TEXT,                   -- human label from config
    gate_sequence TEXT,                     -- 'A,B' or 'B,A'
    line_a_cross_frame INTEGER,             -- frame when crossed line A
    line_b_cross_frame INTEGER,             -- frame when crossed line B
    track_age_frames INTEGER,               -- track age when counted
    track_displacement_px REAL,             -- displacement when counted
    cloud_synced INTEGER DEFAULT 0          -- 0=not synced, 1=synced
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_count_events_ts ON count_events(ts);
CREATE INDEX IF NOT EXISTS idx_count_events_direction ON count_events(direction_code);
CREATE INDEX IF NOT EXISTS idx_count_events_cloud_synced ON count_events(cloud_synced);
