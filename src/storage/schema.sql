-- SQLite schema (matches src/storage/database.py initialize()).

CREATE TABLE IF NOT EXISTS vehicle_detections (
    id INTEGER PRIMARY KEY,
    timestamp REAL NOT NULL,
    date_time TEXT NOT NULL,
    direction TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cloud_synced INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hourly_counts (
    id INTEGER PRIMARY KEY,
    hour_beginning TIMESTAMP NOT NULL,
    vehicle_count INTEGER NOT NULL,
    cloud_synced INTEGER DEFAULT 0,
    UNIQUE(hour_beginning)
);

CREATE TABLE IF NOT EXISTS daily_counts (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    vehicle_count INTEGER NOT NULL,
    cloud_synced INTEGER DEFAULT 0,
    UNIQUE(date)
);


