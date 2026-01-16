#!/bin/bash
# Raspberry Pi Hailo Setup Script
# Safely pulls latest code and verifies Hailo setup

set -e  # Exit on error

echo "=========================================="
echo "Raspberry Pi 5 + Hailo Setup Script"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to traffic-monitor directory
cd ~/traffic-monitor || { echo "Error: ~/traffic-monitor not found"; exit 1; }

echo "📁 Current directory: $(pwd)"
echo ""

# Step 1: Stop any running processes
echo "🛑 Step 1: Stopping background processes..."
python3 src/main.py --stop 2>/dev/null || true
pkill -f "main.py" 2>/dev/null || true
sleep 2
echo -e "${GREEN}✅ Background processes stopped${NC}"
echo ""

# Step 2: Backup config files
echo "💾 Step 2: Backing up configuration..."
mkdir -p ~/traffic-monitor-backups
BACKUP_DIR=~/traffic-monitor-backups/backup-$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUP_DIR"

if [ -f config/config.yaml ]; then
    cp config/config.yaml "$BACKUP_DIR/config.yaml"
    echo -e "${GREEN}✅ config.yaml backed up to: $BACKUP_DIR${NC}"
else
    echo -e "${YELLOW}⚠️  No config.yaml found (this is OK)${NC}"
fi

if [ -f data/calibration/site.yaml ]; then
    cp data/calibration/site.yaml "$BACKUP_DIR/site.yaml"
    echo -e "${GREEN}✅ site.yaml backed up${NC}"
fi
echo ""

# Step 3: Check git status
echo "🔍 Step 3: Checking git status..."
git status
echo ""

# Step 4: Resolve config conflicts
echo "🔧 Step 4: Resolving config conflicts..."

# Check if config.yaml is tracked (it shouldn't be)
if git ls-files --error-unmatch config/config.yaml 2>/dev/null; then
    echo "Removing config.yaml from git tracking..."
    git rm --cached config/config.yaml
    echo "config/config.yaml" >> .gitignore
    git add .gitignore
    git commit -m "Stop tracking config.yaml" || true
fi

# Stash any other local changes
echo "Stashing local changes..."
git stash push -m "Auto-stash before Hailo update $(date +%Y%m%d-%H%M%S)"
echo ""

# Step 5: Pull latest code
echo "⬇️  Step 5: Pulling latest code from git..."
git pull origin main || git pull origin master
echo -e "${GREEN}✅ Code updated${NC}"
echo ""

# Step 6: Restore config
echo "♻️  Step 6: Restoring your configuration..."
if [ -f "$BACKUP_DIR/config.yaml" ]; then
    cp "$BACKUP_DIR/config.yaml" config/config.yaml
    echo -e "${GREEN}✅ config.yaml restored${NC}"
fi
if [ -f "$BACKUP_DIR/site.yaml" ]; then
    mkdir -p data/calibration
    cp "$BACKUP_DIR/site.yaml" data/calibration/site.yaml
    echo -e "${GREEN}✅ site.yaml restored${NC}"
fi
echo ""

# Step 7: Verify new files
echo "📋 Step 7: Verifying Hailo implementation files..."
FILES_OK=true

if [ -f "src/inference/hailo_backend.py" ]; then
    LINES=$(wc -l < src/inference/hailo_backend.py)
    echo -e "${GREEN}✅ hailo_backend.py present ($LINES lines)${NC}"
else
    echo -e "${RED}❌ hailo_backend.py missing${NC}"
    FILES_OK=false
fi

if [ -f "tools/test_hailo.py" ]; then
    LINES=$(wc -l < tools/test_hailo.py)
    echo -e "${GREEN}✅ test_hailo.py present ($LINES lines)${NC}"
else
    echo -e "${RED}❌ test_hailo.py missing${NC}"
    FILES_OK=false
fi

if [ -f "docs/HAILO_SETUP.md" ]; then
    echo -e "${GREEN}✅ HAILO_SETUP.md present${NC}"
else
    echo -e "${RED}❌ HAILO_SETUP.md missing${NC}"
    FILES_OK=false
fi

if grep -q "hailo:" config/default.yaml; then
    echo -e "${GREEN}✅ Hailo config in default.yaml${NC}"
else
    echo -e "${RED}❌ Hailo config missing from default.yaml${NC}"
    FILES_OK=false
fi

echo ""

if [ "$FILES_OK" = false ]; then
    echo -e "${RED}⚠️  Some files are missing. Check git pull output above.${NC}"
    echo ""
fi

# Step 8: Verify Hailo hardware
echo "🔌 Step 8: Verifying Hailo hardware..."

if lspci | grep -q Hailo; then
    echo -e "${GREEN}✅ Hailo HAT detected via PCIe${NC}"
else
    echo -e "${RED}❌ Hailo HAT not detected${NC}"
    echo "   Check HAT is properly seated and reboot"
fi

if command -v hailortcli &> /dev/null; then
    echo -e "${GREEN}✅ HailoRT CLI installed${NC}"
    
    if hailortcli fw-control identify &> /dev/null; then
        echo -e "${GREEN}✅ Hailo device responding${NC}"
        echo ""
        echo "Device info:"
        hailortcli fw-control identify | grep -E "Board Name|Firmware Version|Device Architecture"
    else
        echo -e "${RED}❌ Hailo device not responding${NC}"
    fi
else
    echo -e "${RED}❌ HailoRT not installed${NC}"
    echo "   Run: sudo apt install hailo-all"
fi

echo ""

# Step 9: Test Python bindings
echo "🐍 Step 9: Testing Python bindings..."
python3 << 'PYEOF'
try:
    from hailo_platform import VDevice
    print("✅ Hailo Python bindings imported")
    params = VDevice.create_params()
    device = VDevice(params)
    print("✅ VDevice created successfully")
    print("✅ Hailo Python bindings: WORKING")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("   Run: sudo apt install hailo-all")
except Exception as e:
    print(f"⚠️  Device error: {e}")
    print("   (This might be OK if device was created)")
PYEOF

echo ""

# Step 10: Check for HEF models
echo "🔍 Step 10: Searching for HEF models..."

# Check project directory
if ls data/artifacts/*.hef 1> /dev/null 2>&1; then
    echo -e "${GREEN}✅ HEF models found in data/artifacts:${NC}"
    ls -lh data/artifacts/*.hef
else
    echo -e "${YELLOW}⚠️  No HEF models in data/artifacts/${NC}"
fi

# Check system directories
echo ""
echo "Searching system directories for example HEF files..."
FOUND_HEF=$(find /usr/share -name "*.hef" 2>/dev/null | head -5)
if [ -n "$FOUND_HEF" ]; then
    echo -e "${GREEN}✅ Found example HEF files:${NC}"
    echo "$FOUND_HEF"
else
    echo -e "${YELLOW}⚠️  No example HEF files found in /usr/share${NC}"
fi

echo ""

# Step 11: Check temperature
echo "🌡️  Step 11: Checking temperature..."
TEMP=$(vcgencmd measure_temp 2>/dev/null | sed 's/temp=//;s/'\''C//')
if [ -n "$TEMP" ]; then
    echo "Current temperature: ${TEMP}°C"
    TEMP_NUM=$(echo $TEMP | cut -d. -f1)
    if [ "$TEMP_NUM" -lt 60 ]; then
        echo -e "${GREEN}✅ Temperature good (< 60°C)${NC}"
    elif [ "$TEMP_NUM" -lt 70 ]; then
        echo -e "${YELLOW}⚠️  Temperature acceptable (60-70°C)${NC}"
    else
        echo -e "${RED}⚠️  Temperature high (> 70°C) - check cooling${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Could not read temperature${NC}"
fi

echo ""

# Summary
echo "=========================================="
echo "Setup Summary"
echo "=========================================="
echo ""
echo "Backups saved to: $BACKUP_DIR"
echo ""
echo "Next steps:"
echo "1. If HEF model is missing:"
echo "   - See docs/HAILO_SETUP.md for download/compilation instructions"
echo "2. Once you have a HEF model:"
echo "   - Place it in: ~/traffic-monitor/data/artifacts/"
echo "   - Run: python3 tools/test_hailo.py --hef data/artifacts/yolov8s.hef"
echo "3. Deploy traffic monitor:"
echo "   - Update config/config.yaml to set: detection.backend: hailo"
echo "   - Run: python3 src/main.py --config config/config.yaml"
echo ""
echo "Documentation:"
echo "- Full setup guide: docs/HAILO_SETUP.md"
echo "- Quick start: PI_QUICKSTART.md"
echo "- Deployment checklist: DEPLOYMENT_CHECKLIST.md"
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
