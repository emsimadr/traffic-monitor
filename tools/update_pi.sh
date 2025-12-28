#!/bin/bash
#
# Quick update script for Traffic Monitor on Raspberry Pi
#
# Usage: ./tools/update_pi.sh
#
# This script:
#   1. Stops the service
#   2. Pulls latest code
#   3. Updates Python dependencies
#   4. Rebuilds frontend (if Node.js is installed)
#   5. Restarts the service
#
set -e

APP_NAME="traffic-monitor"
INSTALL_DIR="/opt/$APP_NAME"

echo "Updating Traffic Monitor..."

# Check if we're in the right directory
if [ ! -f "src/main.py" ]; then
    if [ -d "$INSTALL_DIR" ]; then
        cd "$INSTALL_DIR"
    else
        echo "Error: Cannot find traffic-monitor installation"
        exit 1
    fi
fi

# Stop service if running
if systemctl is-active --quiet $APP_NAME; then
    echo "Stopping service..."
    sudo systemctl stop $APP_NAME
fi

# Save config backup
if [ -f "config/config.yaml" ]; then
    cp config/config.yaml /tmp/config.yaml.bak
    echo "Backed up config to /tmp/config.yaml.bak"
fi

# Pull latest code
echo "Pulling latest code..."
git fetch --all
git reset --hard origin/main

# Restore config
if [ -f "/tmp/config.yaml.bak" ]; then
    cp /tmp/config.yaml.bak config/config.yaml
    echo "Restored config"
fi

# Update Python dependencies
echo "Updating Python dependencies..."
source .venv/bin/activate
grep -v '^opencv-python' requirements.txt > /tmp/requirements.pi.txt
pip install -r /tmp/requirements.pi.txt

# Rebuild frontend if npm is available
if command -v npm &> /dev/null && [ -d "frontend" ]; then
    echo "Rebuilding frontend..."
    cd frontend
    npm install
    npm run build
    cd ..
fi

# Start service
echo "Starting service..."
sudo systemctl start $APP_NAME

echo ""
echo "Update complete!"
echo "Check status: sudo journalctl -u $APP_NAME -f"

