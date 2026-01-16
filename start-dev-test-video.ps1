# Development startup script with TEST VIDEO (no camera needed)
# Useful when RTSP camera is offline or no webcam available

Write-Host "🚀 Starting Traffic Monitor (Test Video Mode)" -ForegroundColor Cyan

# Set working directory
Set-Location "C:\Users\Michael\workspace\Coding Projects\traffic-monitor"

# Kill any existing processes on port 5000
Write-Host "Cleaning up port 5000..." -ForegroundColor Yellow
Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | 
    Select-Object OwningProcess | 
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

# Create temporary config with test video
$testConfig = @"
camera:
  backend: opencv
  device_id: "data/artifacts/test_video.mp4"  # Use test video instead of camera
  resolution: [1280, 720]
  fps: 30
  swap_rb: false
  rotate: 0
  flip_horizontal: false
  flip_vertical: false
detection:
  backend: bgsub
  min_contour_area: 1000
counting:
  mode: gate
  line_a:
  - - 0.57
    - 0.26
  - - 0.34
    - 0.83
  line_b:
  - - 0.62
    - 0.31
  - - 0.44
    - 0.87
  direction_labels:
    a_to_b: southbound
    b_to_a: northbound
storage:
  local_database_path: "data/database.sqlite"
  retention_days: 30
  use_cloud_storage: false
  sync_enabled: false
tracking:
  max_frames_since_seen: 10
  min_trajectory_length: 3
  iou_threshold: 0.3
log_path: "logs/traffic_monitor.log"
log_level: "INFO"
"@

$testConfig | Out-File -FilePath "config/config_test_video.yaml" -Encoding utf8

Write-Host "⚠️  Using test video mode (no camera needed)" -ForegroundColor Yellow
Write-Host "Place a test video at: data/artifacts/test_video.mp4" -ForegroundColor Gray

# Start Backend
Write-Host "Starting Backend on port 5000..." -ForegroundColor Green
$env:PYTHONPATH = "src"

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd 'C:\Users\Michael\workspace\Coding Projects\traffic-monitor'; `$env:PYTHONPATH='src'; python src/main.py --config config/config_test_video.yaml"
) -WindowStyle Normal

# Wait for backend to initialize
Start-Sleep -Seconds 3

# Start Frontend
Write-Host "Starting Frontend on port 5173..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd 'C:\Users\Michael\workspace\Coding Projects\traffic-monitor\frontend'; npm run dev"
) -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "`n✅ Development servers started!" -ForegroundColor Green
Write-Host "Backend:  http://localhost:5000" -ForegroundColor White
Write-Host "Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "`nPress Ctrl+C in each terminal window to stop." -ForegroundColor Gray

