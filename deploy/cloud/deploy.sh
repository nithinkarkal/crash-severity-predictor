#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Deploy (or re-deploy) the ASP serving+monitoring stack to the k3s cluster.
# Run ON the Oracle VM, from the repo root of a clone that also has your
# (git-ignored) .env / .env.backend / .env.grafana and artifacts/metrics/.
# Idempotent: safe to re-run.
#
# Required env vars:
#   DOMAIN  your DuckDNS host, e.g. crash-severity.duckdns.org
#   EMAIL   your email for Let's Encrypt, e.g. you@example.com
#
# Usage:
#   export DOMAIN=crash-severity.duckdns.org EMAIL=you@example.com
#   chmod +x deploy/cloud/deploy.sh && ./deploy/cloud/deploy.sh
# ---------------------------------------------------------------------------
set -euo pipefail

: "${DOMAIN:?set DOMAIN=your-subdomain.duckdns.org}"
: "${EMAIL:?set EMAIL=you@example.com}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

# repo root (this script lives in deploy/cloud/)
cd "$(cd "$(dirname "$0")/../.." && pwd)"

echo "==> Namespace"
kubectl create namespace asp --dry-run=client -o yaml | kubectl apply -f -

new_secret() { kubectl create secret generic "$1" --from-env-file="$2" -n asp --dry-run=client -o yaml | kubectl apply -f -; }
new_cmdir()  { kubectl create configmap "$1" --from-file="$2" -n asp --dry-run=client -o yaml | kubectl apply -f -; }

echo "==> Secrets (from .env files)"
new_secret asp-backend-env .env.backend
new_secret asp-dagshub     .env
new_secret asp-grafana-env .env.grafana

echo "==> Config (from monitoring files)"
new_cmdir prometheus-config           infra/monitoring/prometheus/
new_cmdir grafana-datasources         infra/monitoring/grafana/provisioning/datasources/
new_cmdir grafana-dashboard-providers infra/monitoring/grafana/provisioning/dashboards/
new_cmdir grafana-dashboards          infra/monitoring/grafana/dashboards/

echo "==> Metrics configmap (latest run)"
m="$(ls -1 artifacts/metrics/model_*_metrics.json 2>/dev/null | sort | tail -1 || true)"
if [ -n "$m" ]; then
    kubectl create configmap asp-metrics --from-file="$m" -n asp --dry-run=client -o yaml | kubectl apply -f -
else
    echo "   (no metrics json found - home cards will show 0%; scp artifacts/metrics/ to fix)"
fi

echo "==> Let's Encrypt ClusterIssuers"
sed "s/__EMAIL__/${EMAIL}/g" k8s/cloud/cluster-issuer.yaml | kubectl apply -f -

echo "==> Workloads (kustomize cloud overlay, domain=${DOMAIN})"
# LoadRestrictionsNone: the base kustomization (k8s/base) references the manifests in
# the parent k8s/ dir, which kustomize forbids under its default root-only restrictor.
kubectl kustomize --load-restrictor LoadRestrictionsNone k8s/cloud \
    | sed -e "s/__DOMAIN__/${DOMAIN}/g" -e "s/__EMAIL__/${EMAIL}/g" \
    | kubectl apply -f -

echo "==> Waiting for rollouts..."
kubectl rollout status deploy/backend    -n asp --timeout=300s
kubectl rollout status deploy/frontend   -n asp --timeout=300s
kubectl rollout status deploy/grafana    -n asp --timeout=300s
kubectl rollout status deploy/prometheus -n asp --timeout=300s

echo ""
kubectl get pods,ingress,certificate -n asp
echo ""
echo "Open (cert may take 1-2 min on first issue):"
echo "  https://${DOMAIN}/            (GUI)"
echo "  https://${DOMAIN}/grafana/    (dashboards)"
echo "  https://${DOMAIN}/api/v1/health"
