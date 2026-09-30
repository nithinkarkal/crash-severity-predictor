# ---------------------------------------------------------------------------
# Cross-build the backend + frontend images for ARM64 (Oracle Ampere) and push
# to GitHub Container Registry (GHCR). Run on Windows with Docker Desktop.
#
# One-time prerequisites:
#   - A GitHub Personal Access Token (classic) with scope: write:packages
#     Set it as an env var before running:  $env:GHCR_TOKEN = "ghp_xxx"
#   - Docker Desktop running (it ships QEMU, so it can build arm64 on your amd64 PC).
#
# Usage (from the repo root):
#   $env:GHCR_TOKEN = "ghp_xxx"
#   .\deploy\cloud\build_push.ps1
#
# NOTE: cross-building arm64 via emulation is SLOW (20-40 min the first time).
# Faster alternative: build natively ON the Oracle ARM VM (see deploy/cloud/DEPLOY.md).
# ---------------------------------------------------------------------------
param(
    [string]$Owner = "nithinkarkal",
    [string]$Tag = "latest"
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $RepoRoot

if (-not $env:GHCR_TOKEN) {
    throw "Set `$env:GHCR_TOKEN to a GitHub PAT with 'write:packages' scope first."
}

Write-Host "=== Logging in to ghcr.io as $Owner ===" -ForegroundColor Cyan
$env:GHCR_TOKEN | docker login ghcr.io -u $Owner --password-stdin

Write-Host "=== Ensuring a buildx builder exists ===" -ForegroundColor Cyan
if (-not (docker buildx ls | Select-String "asp-builder")) {
    docker buildx create --name asp-builder --use | Out-Null
} else {
    docker buildx use asp-builder
}
docker buildx inspect --bootstrap | Out-Null

$backend = "ghcr.io/$Owner/asp-backend:$Tag"
$frontend = "ghcr.io/$Owner/asp-frontend:$Tag"

Write-Host "=== Building + pushing $backend (linux/arm64) ===" -ForegroundColor Cyan
docker buildx build --platform linux/arm64 `
    -f services/backend/Dockerfile.backend `
    -t $backend --push .

Write-Host "=== Building + pushing $frontend (linux/arm64) ===" -ForegroundColor Cyan
docker buildx build --platform linux/arm64 `
    -f services/frontend/Dockerfile.frontend `
    -t $frontend --push .

Write-Host ""
Write-Host "Done. Pushed:" -ForegroundColor Green
Write-Host "  $backend"
Write-Host "  $frontend"
Write-Host ""
Write-Host "IMPORTANT: make both packages PUBLIC so the VM can pull without a login:" -ForegroundColor Yellow
Write-Host "  github.com/users/$Owner/packages -> each package -> Package settings -> Change visibility -> Public"
