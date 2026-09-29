# Deploy (or re-deploy) the ASP serving+monitoring stack to the current kube context.
# Idempotent: safe to re-run. Assumes the cluster + ingress-nginx exist and images are loaded
# (see k8s/README.md "One-time cluster setup").
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot   # repo root (this script lives in k8s/)
Set-Location $repo

Write-Host "==> Namespace" -ForegroundColor Cyan
kubectl apply -f k8s/00-namespace.yaml

# Idempotent secret/configmap creation via dry-run|apply.
function New-Secret($name, $file) {
    kubectl create secret generic $name --from-env-file=$file -n asp --dry-run=client -o yaml | kubectl apply -f -
}
function New-CMDir($name, $dir) {
    kubectl create configmap $name --from-file=$dir -n asp --dry-run=client -o yaml | kubectl apply -f -
}

Write-Host "==> Secrets (from .env files)" -ForegroundColor Cyan
New-Secret "asp-backend-env" ".env.backend"
New-Secret "asp-dagshub"     ".env"
New-Secret "asp-grafana-env" ".env.grafana"

Write-Host "==> Config (from monitoring files)" -ForegroundColor Cyan
New-CMDir "prometheus-config"           "infra/monitoring/prometheus/"
New-CMDir "grafana-datasources"         "infra/monitoring/grafana/provisioning/datasources/"
New-CMDir "grafana-dashboard-providers" "infra/monitoring/grafana/provisioning/dashboards/"
New-CMDir "grafana-dashboards"          "infra/monitoring/grafana/dashboards/"

Write-Host "==> Metrics configmap (latest run)" -ForegroundColor Cyan
$m = Get-ChildItem artifacts\metrics\model_*_metrics.json | Sort-Object Name | Select-Object -Last 1
if ($null -eq $m) { Write-Host "  (no metrics json found - home cards will show 0%)" -ForegroundColor Yellow }
else { kubectl create configmap asp-metrics --from-file=$($m.FullName) -n asp --dry-run=client -o yaml | kubectl apply -f - }

Write-Host "==> Workloads" -ForegroundColor Cyan
# Apply the numbered manifests only (skip kind-config.yaml, which is a kind cluster file).
Get-ChildItem "$repo\k8s\*.yaml" | Where-Object { $_.Name -ne 'kind-config.yaml' } |
    ForEach-Object { kubectl apply -f $_.FullName }

Write-Host "==> Waiting for rollouts..." -ForegroundColor Cyan
kubectl rollout status deploy/backend  -n asp --timeout=180s
kubectl rollout status deploy/frontend -n asp --timeout=180s
kubectl rollout status deploy/grafana  -n asp --timeout=180s
kubectl rollout status deploy/prometheus -n asp --timeout=180s

Write-Host ""
kubectl get pods,ingress -n asp
Write-Host "`nOpen: http://asp.local/  |  http://asp.local/grafana/  |  http://asp.local/api/v1/health" -ForegroundColor Green
