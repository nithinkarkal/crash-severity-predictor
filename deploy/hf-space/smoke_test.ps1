# ---------------------------------------------------------------------------
# Local smoke test for the HF Space image (run on Windows with Docker Desktop).
# Builds deploy/hf-space/Dockerfile, then runs the container with your EXISTING
# DagsHub token (read from .env) + demo credentials, on http://localhost:7860.
#
# This is a LOCAL test only - it does not touch Hugging Face. Rotate the token
# before the public push, not for this test.
#
# Usage (from the repo root):
#   .\deploy\hf-space\smoke_test.ps1
#   # open http://localhost:7860  -> login is pre-filled demo / demo1234
#   # Ctrl+C to stop, then it auto-removes the container.
# ---------------------------------------------------------------------------
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $RepoRoot

# --- read DagsHub values from .env -----------------------------------------
function Get-EnvVal($file, $key) {
    if (-not (Test-Path $file)) { return $null }
    $line = Select-String -Path $file -Pattern "^\s*$key\s*=" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line.Line -replace "^\s*$key\s*=", "").Trim().Trim('"').Trim("'")
}

$token = Get-EnvVal ".env" "DAGSHUB_USER_TOKEN"
$owner = (Get-EnvVal ".env" "DAGSHUB_REPO_OWNER"); if (-not $owner) { $owner = "nithinkarkal" }
$name  = (Get-EnvVal ".env" "DAGSHUB_REPO_NAME");  if (-not $name)  { $name  = "crash-severity-predictor" }

if (-not $token) {
    throw "DAGSHUB_USER_TOKEN not found in .env - the backend needs it to load the model from the registry."
}

# demo user (bcrypt-b64 hash of 'demo1234' - safe to embed, one-way + salted)
$demoHash = "JDJiJDEyJEtXMlhRRTIzVUI0VnVKLnVTeFVCM2VrdHNYRlpZSmltVjRRMnQuNDVKWWRDZFA3TkJMRkxl"

Write-Host "=== Building image (css-space) ===" -ForegroundColor Cyan
docker build -f deploy/hf-space/Dockerfile -t css-space .

Write-Host ""
Write-Host "=== Running container on http://localhost:7860 ===" -ForegroundColor Cyan
Write-Host "Open the URL, log in (pre-filled demo / demo1234), run a prediction + explanation." -ForegroundColor Yellow
Write-Host "Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

docker run --rm -p 7860:7860 `
    -e DAGSHUB_USER_TOKEN=$token `
    -e DAGSHUB_REPO_OWNER=$owner `
    -e DAGSHUB_REPO_NAME=$name `
    -e JWT_SECRET_KEY=local-smoke-test-secret `
    -e USER_USERNAME=demo `
    -e USER_PASSWORD_HASH_B64=$demoHash `
    -e ADMIN_USERNAME=admin `
    -e CLOUD_DEMO=1 -e DEMO_USERNAME=demo -e DEMO_PASSWORD=demo1234 `
    --name css-space-test `
    css-space
