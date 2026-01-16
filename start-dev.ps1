# Development startup script for Traffic Monitor
# Starts both backend and frontend servers

Write-Host "🚀 Starting Traffic Monitor Development Environment" -ForegroundColor Cyan

# Set working directory
Set-Location "C:\Users\Michael\workspace\Coding Projects\traffic-monitor"

# Activate venv for this script
& ".venv/Scripts/Activate.ps1"

# Start Backend (Python) with --kill-existing to handle any lingering processes
Write-Host "Starting Backend on port 5000..." -ForegroundColor Green
$env:PYTHONPATH = "src"
$env:OPENCV_FFMPEG_CAPTURE_OPTIONS = "rtsp_transport;tcp"

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd 'C:\Users\Michael\workspace\Coding Projects\traffic-monitor'; & '.venv/Scripts/Activate.ps1'; `$env:PYTHONPATH='src'; `$env:OPENCV_FFMPEG_CAPTURE_OPTIONS='rtsp_transport;tcp'; python src/main.py --config config/config.yaml --kill-existing"
) -WindowStyle Normal

# Wait for backend to initialize (loading config, camera, model)
Write-Host "Waiting for backend to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 8

# Start Frontend (Vite)
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
Write-Host "`nTo stop: run .\stop-dev.ps1 or press Ctrl+C in each terminal" -ForegroundColor Gray

