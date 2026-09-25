# ============================================================
# START_ALL.ps1 — STRATA 3D-Mapping full local stack launcher
# Run from project root: powershell -ExecutionPolicy Bypass -File START_ALL.ps1
# ============================================================
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

Write-Host "`n=== STRATA 3D-Mapping Startup ===" -ForegroundColor Cyan

# Step 1: Start Docker Desktop if not running
Write-Host "`n[1/6] Checking Docker daemon..." -ForegroundColor Yellow
$dockerOk = $false
try {
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch {}

if (-not $dockerOk) {
    $ddExe = "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe"
    if (Test-Path $ddExe) {
        Write-Host "     Starting Docker Desktop..." -ForegroundColor Gray
        Start-Process $ddExe -WindowStyle Minimized
    } else {
        Write-Host "ERROR: Docker Desktop not found." -ForegroundColor Red; exit 1
    }
    $waited = 0
    while ($waited -lt 120) {
        Start-Sleep -Seconds 5; $waited += 5
        try { docker ps 2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break } } catch {}
        Write-Host "     Waiting for Docker... ${waited}/120s" -ForegroundColor Gray
    }
    if (-not $dockerOk) { Write-Host "ERROR: Docker daemon did not start." -ForegroundColor Red; exit 1 }
}
Write-Host "     Docker daemon is ready." -ForegroundColor Green

# Step 2: Start docker-compose services
Write-Host "`n[2/6] Starting docker-compose services..." -ForegroundColor Yellow
Set-Location $Root
docker compose up -d db redis backend 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: docker-compose failed." -ForegroundColor Red; exit 1 }

# Step 3: Wait for DB
Write-Host "`n[3/6] Waiting for PostgreSQL..." -ForegroundColor Yellow
$waited = 0
while ($waited -lt 60) {
    $cid = (docker compose ps -q db 2>&1).Trim()
    $health = (docker inspect --format="{{.State.Health.Status}}" $cid 2>&1).Trim()
    if ($health -eq "healthy") { Write-Host "     PostgreSQL healthy." -ForegroundColor Green; break }
    Start-Sleep -Seconds 3; $waited += 3
    Write-Host "     DB: $health  ($waited/60s)" -ForegroundColor Gray
}

# Step 4: Alembic migrations
Write-Host "`n[4/6] Running Alembic migrations..." -ForegroundColor Yellow
docker compose exec -T backend alembic upgrade head 2>&1
Write-Host "     Migrations done." -ForegroundColor Green

# Step 5: Seed superadmin
Write-Host "`n[5/6] Seeding superadmin..." -ForegroundColor Yellow
docker compose exec -T backend python scripts/create_superadmin.py 2>&1

# Step 6: Start Vite frontend
Write-Host "`n[6/6] Starting Vite frontend on http://localhost:5173..." -ForegroundColor Yellow
$frontendDir = Join-Path $Root "frontend"
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Push-Location $frontendDir; npm install; Pop-Location
}
Write-Host "`nSTRATA Running: Frontend→http://localhost:5173 | API→http://localhost:8000 | Docs→http://localhost:8000/docs`n" -ForegroundColor Cyan
Push-Location $frontendDir
npm run dev
Pop-Location
