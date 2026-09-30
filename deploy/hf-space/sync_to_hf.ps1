# ---------------------------------------------------------------------------
# Copy the curated file set from this repo into a local clone of the HF Space,
# so the Space stays small (source only - HF builds the image).
#
# Usage (from anywhere):
#   git clone https://huggingface.co/spaces/<user>/crash-severity-predictor C:\hf\css
#   .\deploy\hf-space\sync_to_hf.ps1 -SpaceDir C:\hf\css
#   cd C:\hf\css ; git add -A ; git commit -m "deploy" ; git push
# ---------------------------------------------------------------------------
param(
    [Parameter(Mandatory = $true)]
    [string]$SpaceDir
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path

if (-not (Test-Path $SpaceDir)) {
    throw "Space directory '$SpaceDir' does not exist. Clone the HF Space there first."
}

Write-Host "Repo root : $RepoRoot"
Write-Host "Space dir : $SpaceDir"
Write-Host ""

# Excludes for the recursive copies
$exclude = @("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache", ".mypy_cache")

function Copy-Tree($name) {
    $src = Join-Path $RepoRoot $name
    $dst = Join-Path $SpaceDir $name
    Write-Host "  copy dir  $name"
    # robocopy mirrors and honours excludes; /NFL /NDL keep output quiet
    robocopy $src $dst /MIR /XD __pycache__ .pytest_cache .ruff_cache .mypy_cache /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
}

# Source trees
Copy-Tree "common"
Copy-Tree "services"
Copy-Tree ".streamlit"

# Single files
Write-Host "  copy file pyproject.toml"
Copy-Item (Join-Path $RepoRoot "pyproject.toml") (Join-Path $SpaceDir "pyproject.toml") -Force
Write-Host "  copy file uv.lock"
Copy-Item (Join-Path $RepoRoot "uv.lock") (Join-Path $SpaceDir "uv.lock") -Force

# HF-specific files -> Space root
Write-Host "  copy file Dockerfile"
Copy-Item (Join-Path $PSScriptRoot "Dockerfile") (Join-Path $SpaceDir "Dockerfile") -Force
Write-Host "  copy file start.sh"
Copy-Item (Join-Path $PSScriptRoot "start.sh") (Join-Path $SpaceDir "start.sh") -Force
Write-Host "  copy file README.md (with HF front-matter)"
Copy-Item (Join-Path $PSScriptRoot "README.md") (Join-Path $SpaceDir "README.md") -Force
Write-Host "  copy file .dockerignore"
Copy-Item (Join-Path $PSScriptRoot ".dockerignore") (Join-Path $SpaceDir ".dockerignore") -Force

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  cd $SpaceDir"
Write-Host "  git add -A ; git commit -m 'deploy crash-severity-predictor' ; git push"
