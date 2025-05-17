# Neighborhood Traffic Monitoring Project

## Problem Statement

Our residential street has become increasingly dangerous due to high traffic volumes and reckless driving behavior, creating an unsafe environment for residents, pedestrians, and especially children. Despite frequent close calls and community concerns, we lack the quantitative data necessary to compel municipal action. Current traffic management prioritizes vehicle flow over neighborhood livability, putting vulnerable road users at risk daily.

We need to systematically collect and analyze comprehensive traffic data to build an evidence-based case for implementing traffic calming measures such as speed bumps, enhanced signage, and integrated road design that prioritizes safety for all users. By documenting actual traffic patterns, speeds, pedestrian presence, and dangerous behaviors, we aim to shift the conversation from anecdotal complaints to data-driven solutions that transform our street from a thoroughfare to a livable community space where all road users can safely coexist.

## Project Overview

This project uses a Raspberry Pi 4 with a webcam to create an automated traffic monitoring system capable of:
- Counting vehicles and measuring their speeds
- Detecting and counting pedestrians (with/without strollers or wheelchairs)
- Tracking bicycle traffic
- Visualizing vehicle travel paths as heatmaps
- Generating reports and visualizations for community advocacy

## Project Structure

```
traffic_monitor/
│
├── docs/
│   ├── roadmap.md                 # Development roadmap
│   ├── setup_guide.md             # Hardware setup instructions
│   └── calibration_guide.md       # Camera calibration guide
│
├── src/
│   ├── main.py                    # Main application entry point
│   ├── config.py                  # Configuration handling
│   ├── camera/                    # Camera module
│   │   ├── __init__.py
│   │   ├── capture.py             # Video capture
│   │   └── calibration.py         # Camera calibration tools
│   │
│   ├── detection/                 # Detection modules
│   │   ├── __init__.py
│   │   ├── vehicle.py             # Vehicle detection
│   │   ├── pedestrian.py          # Pedestrian detection
│   │   └── bicycle.py             # Bicycle detection
│   │
│   ├── tracking/                  # Tracking modules
│   │   ├── __init__.py
│   │   ├── object_tracker.py      # Object tracking base class
│   │   └── path_tracker.py        # Path tracking for heatmaps
│   │
│   ├── speed/                     # Speed calculation
│   │   ├── __init__.py
│   │   ├── boundaries.py          # Boundary definitions
│   │   └── calculator.py          # Speed calculation
│   │
│   ├── storage/                   # Data storage
│   │   ├── __init__.py
│   │   ├── database.py            # Database management
│   │   └── models.py              # Data models
│   │
│   └── visualization/             # Visualization tools
│       ├── __init__.py
│       ├── dashboard.py           # Basic dashboard
│       ├── reports.py             # Report generation
│       └── heatmap.py             # Heatmap generation
│
├── tools/                         # Utility scripts
│   ├── setup_system.py            # Initial setup script
│   ├── calibrate_camera.py        # Camera calibration tool
│   └── generate_report.py         # Report generation tool
│
├── data/                          # Data directory
│   ├── config.yaml                # Configuration file
│   └── database.sqlite            # SQLite database (created at runtime)
│
└── requirements.txt               # Python dependencies
```

## Hardware Requirements

- Raspberry Pi 4 (4GB+ RAM recommended)
- USB webcam (minimum 720p resolution)
- Stable mounting solution for camera
- Power supply for Raspberry Pi
- SD card (32GB+ recommended)
- Optional: External hard drive for video storage

## Software Dependencies

```
opencv-python>=4.5.0
numpy>=1.19.0
scipy>=1.6.0
pandas>=1.2.0
matplotlib>=3.3.0
pyyaml>=5.4.0
SQLAlchemy>=1.4.0
imutils>=0.5.4
```

## Getting Started

1. Clone this repository to your Raspberry Pi
2. Install dependencies: `pip install -r requirements.txt`
3. Configure your settings in `data/config.yaml`
4. Run the camera calibration: `python tools/calibrate_camera.py`
5. Start the system: `python src/main.py`

## Development Roadmap

The project is organized into the following development milestones:

### Milestone 1: Core Vehicle Detection & Data Collection
- Basic system setup and vehicle counting

### Milestone 2: Speed Measurement System
- Speed calculation for passing vehicles

### Milestone 3: Pedestrian Detection & Classification
- Detection of pedestrians, with/without strollers or wheelchairs

### Milestone 4: Bicycle Detection
- Detection and counting of bicycle traffic

### Milestone 5: Path Tracking & Heatmap Visualization
- Visualization of vehicle travel paths

### Milestone 6: System Integration & Refinement
- System optimization and dashboard creation

### Milestone 7: Advanced Features
- Additional analytics and classification capabilities

### Milestone 8: Data Presentation & Advocacy
- Tools for community presentations and advocacy

For detailed information on each milestone, see `docs/roadmap.md`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
