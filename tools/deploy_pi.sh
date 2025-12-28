#!/bin/bash
#
# Raspberry Pi Deployment Script for Traffic Monitor
#
# Usage:
#   curl -sSL <raw-url> | bash
#   OR
#   ./tools/deploy_pi.sh
#
# This script:
#   1. Installs system dependencies
#   2. Sets up the application in /opt/traffic-monitor
#   3. Creates a Python venv with system site-packages (for picamera2)
#   4. Installs Python dependencies
#   5. Creates and enables a systemd service
#
set -e

APP_NAME="traffic-monitor"
INSTALL_DIR="/opt/$APP_NAME"
SERVICE_USER="traffic"
REPO_URL="https://github.com/emsimadr/traffic-monitor.git"

echo "=========================================="
echo "Traffic Monitor - Raspberry Pi Deployment"
echo "=========================================="

# Check if running as root for system-wide install
if [ "$EUID" -ne 0 ]; then
    echo "Note: Running without root. Will use sudo for system commands."
    SUDO="sudo"
else
    SUDO=""
fi

# Step 1: Install system dependencies
echo ""
echo "[1/6] Installing system dependencies..."
$SUDO apt update
$SUDO apt install -y \
    git \
    python3 \
    python3-venv \
    python3-pip \
    python3-opencv \
    python3-picamera2 \
    python3-numpy \
    rpicam-apps

# Step 2: Create service user if it doesn't exist
echo ""
echo "[2/6] Setting up service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    $SUDO useradd -r -s /bin/bash -m -d /home/$SERVICE_USER $SERVICE_USER
    $SUDO usermod -aG video $SERVICE_USER
    echo "Created user: $SERVICE_USER"
else
    echo "User $SERVICE_USER already exists"
fi

# Step 3: Clone or update the repository
echo ""
echo "[3/6] Setting up application directory..."
if [ -d "$INSTALL_DIR" ]; then
    echo "Directory exists. Updating..."
    cd "$INSTALL_DIR"
    $SUDO -u $SERVICE_USER git fetch --all
    $SUDO -u $SERVICE_USER git reset --hard origin/main
else
    echo "Cloning repository..."
    $SUDO mkdir -p "$INSTALL_DIR"
    $SUDO chown $SERVICE_USER:$SERVICE_USER "$INSTALL_DIR"
    $SUDO -u $SERVICE_USER git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Step 4: Create Python virtual environment
echo ""
echo "[4/6] Setting up Python environment..."
if [ -d ".venv" ]; then
    echo "Removing old venv..."
    $SUDO rm -rf .venv
fi

$SUDO -u $SERVICE_USER python3 -m venv --system-site-packages .venv
$SUDO -u $SERVICE_USER .venv/bin/python -m pip install -U pip setuptools wheel

# Install requirements (skip opencv-python since we use system opencv)
$SUDO -u $SERVICE_USER bash -c "grep -v '^opencv-python' requirements.txt > /tmp/requirements.pi.txt"
$SUDO -u $SERVICE_USER .venv/bin/pip install -r /tmp/requirements.pi.txt

# Step 5: Create required directories
echo ""
echo "[5/6] Creating data directories..."
$SUDO -u $SERVICE_USER mkdir -p "$INSTALL_DIR/data"
$SUDO -u $SERVICE_USER mkdir -p "$INSTALL_DIR/logs"
$SUDO -u $SERVICE_USER mkdir -p "$INSTALL_DIR/secrets"

# Copy secrets if they exist in home directory
if [ -f "/home/$SERVICE_USER/camera_secrets.yaml" ]; then
    cp /home/$SERVICE_USER/camera_secrets.yaml "$INSTALL_DIR/secrets/"
    chown $SERVICE_USER:$SERVICE_USER "$INSTALL_DIR/secrets/camera_secrets.yaml"
    chmod 600 "$INSTALL_DIR/secrets/camera_secrets.yaml"
    echo "Copied camera_secrets.yaml"
fi

if [ -f "/home/$SERVICE_USER/gcp-credentials.json" ]; then
    cp /home/$SERVICE_USER/gcp-credentials.json "$INSTALL_DIR/secrets/"
    chown $SERVICE_USER:$SERVICE_USER "$INSTALL_DIR/secrets/gcp-credentials.json"
    chmod 600 "$INSTALL_DIR/secrets/gcp-credentials.json"
    echo "Copied gcp-credentials.json"
fi

# Step 6: Create systemd service
echo ""
echo "[6/6] Creating systemd service..."
$SUDO tee /etc/systemd/system/$APP_NAME.service > /dev/null << EOF
[Unit]
Description=Traffic Monitor Service
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/.venv/bin:/usr/bin"
ExecStart=$INSTALL_DIR/.venv/bin/python src/main.py --config config/config.yaml
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

$SUDO systemctl daemon-reload
$SUDO systemctl enable $APP_NAME

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Copy your secrets to the Pi:"
echo "   scp secrets/camera_secrets.yaml traffic@<pi>:$INSTALL_DIR/secrets/"
echo "   scp secrets/gcp-credentials.json traffic@<pi>:$INSTALL_DIR/secrets/"
echo ""
echo "2. Create/edit your config overrides:"
echo "   sudo -u $SERVICE_USER nano $INSTALL_DIR/config/config.yaml"
echo ""
echo "3. Start the service:"
echo "   sudo systemctl start $APP_NAME"
echo ""
echo "4. Check status:"
echo "   sudo systemctl status $APP_NAME"
echo "   sudo journalctl -u $APP_NAME -f"
echo ""
echo "5. Access the web interface:"
echo "   http://$(hostname).local:5000"
echo ""

