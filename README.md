# Neighborhood Traffic Monitoring System

A hybrid edge-cloud architecture for monitoring and analyzing traffic patterns on residential streets using a Raspberry Pi with webcam and Google Cloud Platform for data processing.

## Problem Statement

Our residential street has become increasingly dangerous due to high traffic volumes and reckless driving, creating an unsafe environment for residents, pedestrians, and especially children. Despite frequent close calls and community concerns, we lack the quantitative data necessary to compel municipal action for traffic calming measures.

This project systematically collects and analyzes traffic data to build an evidence-based case for implementing traffic calming measures such as speed bumps, enhanced signage, and integrated road design that prioritizes safety for all road users.

## Project Architecture

The system uses a hybrid edge-cloud architecture:

### Edge Component (Raspberry Pi)
- Captures video from webcam
- Performs real-time vehicle detection and counting
- Temporarily stores data locally
- Syncs data to the cloud on a regular schedule
- Operates with fallback mechanisms for connectivity issues

### Cloud Component (Google Cloud Platform)
- Stores the complete dataset
- Performs advanced analytics and processing
- Handles visualization and reporting
- Provides dashboards and APIs for data access
- Scales resources as needed for intensive tasks

![System Architecture](docs/images/architecture-diagram.png)

## Project Structure

```
traffic_monitor/
│
├── docs/                        # Documentation
│   ├── images/                  # Documentation images
│   ├── roadmap.md               # Development roadmap
│   ├── milestone1_plan.md       # Milestone 1 details
│   ├── setup_guide.md           # Hardware setup instructions
│   └── calibration_guide.md     # Camera calibration guide
│
├── src/                         # Source code
│   ├── main.py                  # Main application entry point
│   ├── camera/                  # Camera module
│   │   ├── __init__.py
│   │   └── capture.py           # Video capture functionality
│   │
│   ├── detection/               # Detection modules
│   │   ├── __init__.py
│   │   └── vehicle.py           # Vehicle detection (Milestone 1)
│   │
│   ├── storage/                 # Local storage
│   │   ├── __init__.py
│   │   └── database.py          # SQLite database handling
│   │
│   ├── cloud/                   # Cloud integration
│   │   ├── __init__.py
│   │   ├── sync.py              # Cloud synchronization
│   │   ├── auth.py              # GCP authentication
│   │   └── utils.py             # Cloud utilities
│   │
│   └── visualization/           # Data visualization (future)
│       └── __init__.py
│
├── tools/                       # Utility scripts
│   ├── setup_system.py          # System setup helper
│   └── test_cloud_connection.py # Cloud connectivity test
│
├── config/                      # Configuration files
│   ├── config.yaml              # Main configuration
│   └── cloud_config.yaml        # Cloud-specific configuration
│
├── data/                        # Data directory
│   └── database.sqlite          # Local SQLite database
│
├── logs/                        # System logs
│
├── secrets/                     # Credentials (gitignored)
│   └── gcp-credentials.json     # GCP service account key
│
└── requirements.txt             # Python dependencies
```

## Development Roadmap

The project is implemented through 8 progressive milestones:

1. **Core Vehicle Detection & Data Collection** (Current)
   - Basic vehicle detection and counting
   - Local and cloud data storage
   - Initial synchronization

2. **Speed Measurement System**
   - Camera calibration
   - Speed calculation
   - Enhanced data collection

3. **Pedestrian Detection & Classification**
   - Pedestrian identification
   - Classification (adults, children, strollers, etc.)
   - Expanded database schema

4. **Bicycle Detection Integration**
   - Bicycle detection and counting
   - Integration with existing components
   - Multi-modal traffic analysis

5. **Path Tracking & Heatmap Visualization**
   - Track movement patterns
   - Create heatmaps of vehicle paths
   - GCP-based visualization

6. **System Integration & Refinement**
   - Comprehensive data integration
   - Performance optimization
   - Enhanced synchronization

7. **Advanced Features & Expansion**
   - Additional detection capabilities
   - Machine learning enhancements
   - Multi-camera support (optional)

8. **Data Presentation & Advocacy**
   - Create compelling data visualizations
   - Generate reports for municipal advocacy
   - Develop presentation materials

## Hardware Requirements

- Raspberry Pi 4 (4GB+ RAM recommended)
- USB webcam (minimum 720p resolution)
- Stable mounting solution for second-floor window
- Power supply for Raspberry Pi
- SD card (32GB+ recommended)
- Optional: External hard drive for video storage
- Reliable Internet connection

## Software Requirements

### Raspberry Pi
- Raspberry Pi OS (Bullseye or newer)
- Python 3.7+
- OpenCV, NumPy, PyYAML
- Google Cloud client libraries

### Google Cloud Platform
- Google Cloud project with:
  - Cloud Storage
  - BigQuery
  - Cloud Functions (optional)
  - Looker Studio (for dashboards)

## Installation

### 1. Raspberry Pi Setup

1. Install Raspberry Pi OS on SD card
2. Connect to network and enable SSH
3. Update system packages:
   ```
   sudo apt update
   sudo apt upgrade
   ```
4. Install required packages:
   ```
   sudo apt install python3-pip python3-opencv
   ```

### 2. Clone Repository and Install Dependencies

```
git clone https://github.com/your-username/traffic-monitor.git
cd traffic-monitor
pip3 install -r requirements.txt
```

### 3. Google Cloud Platform Setup

1. Create a GCP project in the [Google Cloud Console](https://console.cloud.google.com/)
2. Enable required APIs:
   - Cloud Storage API
   - BigQuery API
3. Create a service account with the following roles:
   - Storage Object Admin
   - BigQuery Data Editor
4. Download service account key JSON file to `secrets/gcp-credentials.json`
5. Create Cloud Storage bucket and BigQuery dataset

### 4. Configure System

1. Edit settings in `config/config.yaml` to match your hardware setup (overrides)
2. Review defaults in `config/default.yaml` (checked in)
3. Configure cloud integration in `config/cloud_config.yaml`
3. Position webcam to properly view the street
4. Test camera connection:
   ```
   python3 tools/test_camera.py
   ```
5. Test cloud connection:
   ```
   python3 tools/test_cloud_connection.py
   ```

### 5. Run the System

```
# Run with visualization (for testing)
python3 src/main.py --config config/config.yaml --display

# Run headless (for deployment)
python3 src/main.py --config config/config.yaml

# Record video samples
python3 src/main.py --config config/config.yaml --record
```

## Using the Data

### Accessing Local Data

The SQLite database (`data/database.sqlite`) contains:
- Individual vehicle detection events
- Hourly and daily aggregate counts

### Accessing Cloud Data

#### BigQuery
- Run queries and analysis on the full dataset
- Create views for common analysis patterns
- Connect to data visualization tools

#### Looker Studio
- Create dashboards for traffic patterns
- Generate visualizations for advocacy
- Share insights with community members

## Data Privacy Considerations

This system is designed to monitor traffic patterns only, not identify individuals:
- No identifying information is collected
- Video is processed for counting and analysis, not surveillance
- Data is anonymized and aggregated
- Installation location should respect community privacy

## Contributing

Contributions to improve the system are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -m 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Open a Pull Request

## Troubleshooting

### Raspberry Pi Issues
- Camera not detected: Verify USB connection and try different ports
- Performance problems: Reduce resolution or FPS in configuration
- Overheating: Ensure adequate ventilation for the Pi

### Cloud Integration Issues
- Authentication errors: Check credentials file and permissions
- Sync failures: Verify internet connection and retry logic
- BigQuery errors: Confirm schema matches between local and cloud

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenCV community for computer vision tools
- Google Cloud documentation and examples
- Raspberry Pi community for edge computing guides
