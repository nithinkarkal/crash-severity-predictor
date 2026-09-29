# Kubernetes deployment (local, via kind)

Deploys the **serving + monitoring** stack to Kubernetes: `backend`, `frontend`, `prometheus`,
`grafana`, `node-exporter`, behind a single **Ingress** at `http://asp.local`.

> **Scope:** serving + monitoring only. The GUI training trigger uses Docker-out-of-Docker, which
> is a compose-only feature; the k8s-native equivalent is a Job (future work). The served model is
> loaded from the MLflow registry on DagsHub at runtime, so no dataset volume is needed.

## Prerequisites

- Docker Desktop, [`kind`](https://kind.sigs.k8s.io/), and `kubectl`.
- The images built locally: `docker compose build backend frontend` (produces `asp-backend:latest`,
  `asp-frontend:latest`).
- Your local `.env`, `.env.backend`, `.env.grafana` present (secrets are created from these — never
  committed).
- `127.0.0.1 asp.local` in your hosts file (you already have this from the compose setup).

## One-time cluster setup

```powershell
# 1. Create the cluster (host ports 80/443 mapped)
kind create cluster --config k8s/kind-config.yaml

# 2. Install the ingress-nginx controller (kind build) and wait for it
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx --for=condition=ready pod `
  --selector=app.kubernetes.io/component=controller --timeout=180s

# 3. Load the locally-built images into the cluster (kind can't pull them from a registry)
kind load docker-image asp-backend:latest asp-frontend:latest --name asp
```

## Deploy the app

Run the helper (creates namespace, secrets-from-.env, config-from-files, then applies manifests):

```powershell
.\k8s\deploy.ps1
```

…or do it manually:

```powershell
kubectl apply -f k8s/00-namespace.yaml

# Secrets (from your local env files — nothing is committed)
kubectl create secret generic asp-backend-env  --from-env-file=.env.backend -n asp
kubectl create secret generic asp-dagshub       --from-env-file=.env         -n asp
kubectl create secret generic asp-grafana-env   --from-env-file=.env.grafana -n asp

# Config (reuse the existing monitoring files)
kubectl create configmap prometheus-config          --from-file=infra/monitoring/prometheus/ -n asp
kubectl create configmap grafana-datasources        --from-file=infra/monitoring/grafana/provisioning/datasources/ -n asp
kubectl create configmap grafana-dashboard-providers --from-file=infra/monitoring/grafana/provisioning/dashboards/ -n asp
kubectl create configmap grafana-dashboards          --from-file=infra/monitoring/grafana/dashboards/ -n asp

# Real evaluation metrics (latest run) so /model/info shows live numbers
$m = Get-ChildItem artifacts\metrics\model_*_metrics.json | Sort-Object Name | Select-Object -Last 1
kubectl create configmap asp-metrics --from-file=$($m.FullName) -n asp

# The workloads
kubectl apply -f k8s/
```

## Access

- GUI:      http://asp.local/
- API:      http://asp.local/api/v1/health
- Grafana:  http://asp.local/grafana/

Logins are the same as compose (admin / datascientest). All traffic is HTTP on one host, so the
Grafana embed works with **no certificate step** (unlike the local TLS compose setup).

## Check / debug

```powershell
kubectl get pods -n asp
kubectl get ingress -n asp
kubectl logs -n asp deploy/backend
kubectl describe pod -n asp -l app=backend
```

## Tear down

```powershell
kubectl delete namespace asp        # remove the app
kind delete cluster --name asp      # remove the whole cluster
```

> Tip: stop the compose stack (`docker compose down`) while running kind, so they don't fight over
> ports/resources.
