# Start script for Cost Estimator AI Agent

$BackendDir = "backend"
$FrontendDir = "frontend"

Write-Host "🚀 Starting Cost Estimator AI Agent..." -ForegroundColor Cyan

# Start Backend
Write-Host "📦 Starting Backend API (Port 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd $BackendDir; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

# Start Frontend
Write-Host "💻 Starting Frontend UI (Port 5173)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd $FrontendDir; npm run dev -- --port 5173 --host"

Write-Host "✅ Both servers are launching in separate windows." -ForegroundColor Green
Write-Host "🔗 Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "🔗 API Docs: http://localhost:8000/docs" -ForegroundColor Green
