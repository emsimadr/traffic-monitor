# Stop Traffic Monitor cleanly
# This script stops any running instance of the traffic monitor

Write-Host "🛑 Stopping Traffic Monitor..." -ForegroundColor Yellow

Set-Location "C:\Users\Michael\workspace\Coding Projects\traffic-monitor"

# Activate venv and run stop command
$env:PYTHONPATH = "src"
& ".venv/Scripts/python.exe" src/main.py --stop

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Traffic Monitor stopped" -ForegroundColor Green
} else {
    Write-Host "⚠️  No instance was running or failed to stop" -ForegroundColor Yellow
    
    # Fallback: kill any Python processes on port 5000
    Write-Host "Checking for processes on port 5000..." -ForegroundColor Gray
    $conn = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | 
            Where-Object { $_.State -eq 'Listen' }
    if ($conn) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Killing process: $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Yellow
            Stop-Process -Id $proc.Id -Force
        }
    }
}

Write-Host ""

