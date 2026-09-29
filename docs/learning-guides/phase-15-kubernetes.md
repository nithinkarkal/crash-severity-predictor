# Phase 15 — Kubernetes (serving + monitoring on `kind`)

> **Goal of this phase:** take the Docker-Compose stack and run it on **Kubernetes** — the same
> images, now as Deployments/Services behind a single **Ingress** — tested locally on **kind** with
> no cloud and no cost. You'll learn how each compose service maps to k8s objects, how config and
> secrets are supplied without duplication, and why an HTTP Ingress on one host makes the Grafana
> embed "just work."

This is the first of the two closing infrastructure phases (15 Kubernetes → 16 cloud). We scope it
to **serving + monitoring**; training stays a compose feature (see §15.6).

---

## 15.1 Compose vs Kubernetes — the mental shift

Compose is one machine, imperative-ish (`up`/`down`). Kubernetes is a **declarative cluster**: you
describe the desired state (objects) and the control plane makes it so, restarts crashed pods, and
can scale replicas. The building blocks:

- **Deployment** — "keep N copies of this container running" (self-healing).
- **Service** — a stable in-cluster DNS name + load-balancer in front of a Deployment's pods.
- **ConfigMap / Secret** — non-secret / secret key-value config injected as env or files.
- **PersistentVolumeClaim (PVC)** — durable storage (Prometheus TSDB, Grafana DB).
- **DaemonSet** — one pod **per node** (node-exporter, which reads host metrics).
- **Ingress** — the single HTTP entrypoint with host/path routing (replaces the compose nginx).

## 15.2 The mapping

| Compose service | Kubernetes | File |
|---|---|---|
| backend | Deployment + Service + ConfigMap + Secrets | `k8s/10-backend.yaml` |
| frontend | Deployment + Service | `k8s/20-frontend.yaml` |
| prometheus | Deployment + Service + PVC (+ ConfigMap) | `k8s/30-prometheus.yaml` |
| node-exporter | **DaemonSet** + Service | `k8s/31-node-exporter.yaml` |
| grafana | Deployment + Service + PVC (+ ConfigMaps) | `k8s/40-grafana.yaml` |
| nginx | **Ingress** | `k8s/50-ingress.yaml` |

Key trick: the k8s **Service names are identical to the compose service names** (`backend`,
`prometheus`, `node-exporter`), so the existing `prometheus.yml` scrape targets and the Grafana
datasource URL (`http://prometheus:9090`) work **unchanged**.

## 15.3 Config & secrets — reuse, don't duplicate

Rather than re-typing config into YAML, we build ConfigMaps/Secrets straight from the files that
already exist:

```powershell
# secrets from your local env files (nothing committed)
kubectl create secret generic asp-backend-env --from-env-file=.env.backend -n asp
# config from the monitoring files
kubectl create configmap prometheus-config --from-file=infra/monitoring/prometheus/ -n asp
kubectl create configmap grafana-dashboards --from-file=infra/monitoring/grafana/dashboards/ -n asp
```

The Deployments reference them via `envFrom`/`secretRef` (env) and `volumeMounts` (files). Secrets
never enter git — they're created imperatively from your `.env*`. (`k8s/deploy.ps1` automates all of
this idempotently.)

Two small but important details in the manifests:

- **`imagePullPolicy: IfNotPresent`** on backend/frontend — kind can't pull `asp-backend:latest`
  from a registry, so we `kind load docker-image` them and tell k8s to use the local copy.
- **`securityContext.fsGroup`** on Prometheus (65534) and Grafana (472) — makes the mounted PVC
  writable by the non-root user each image runs as.
- Backend mounts an `asp-metrics` ConfigMap at `/app/artifacts/metrics` so `/model/info` (and the
  GUI home cards) show **real** accuracy/F1 — the serving image ships that folder empty.

## 15.4 One entrypoint — the Ingress

`k8s/50-ingress.yaml` routes host `asp.local` by path: `/api` → backend, `/grafana` → grafana,
`/` → frontend (ingress-nginx matches the longest prefix, so the specific paths win). It also sets
long proxy timeouts so Streamlit's websocket stays open.

**Why this fixes the Grafana embed for free:** locally it's all **HTTP on one host** — no
self-signed certificate, and ingress-nginx doesn't add `X-Frame-Options`, while Grafana runs with
`allow_embedding=true`. So the dashboards embed with zero cert clicking (the pain we had on the
compose TLS setup). On the cloud (phase 16) we put real TLS in front and it stays clean.

## 15.5 What we deliberately left out

The GUI **training trigger** launches a container via the Docker socket (Docker-out-of-Docker).
Kubernetes doesn't do that — the native pattern is for the backend to create a **Job** via the k8s
API (with RBAC). We scoped that out of phase 15; the served model is pulled from the MLflow registry
at runtime, so serving + monitoring need no dataset volume. Training remains available via compose
and the Airflow DAG.

## 15.6 Reproduce it yourself

```powershell
# one-time: cluster + ingress + load images
kind create cluster --config k8s/kind-config.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait -n ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=180s
kind load docker-image asp-backend:latest asp-frontend:latest --name asp

# deploy the app (secrets/config/manifests)
.\k8s\deploy.ps1
```

Then open **http://asp.local/** (GUI), **/grafana/** (dashboards), **/api/v1/health** (API).
`kubectl get pods -n asp` should show everything `Running`/`Ready`.

## 15.7 Phase 15 checkpoint

You understand Phase 15 when you can explain:

- The compose→k8s object mapping, and why naming Services after the compose services keeps
  Prometheus/Grafana config unchanged.
- Deployment vs Service vs Ingress vs PVC vs DaemonSet, and why node-exporter is a DaemonSet.
- How ConfigMaps/Secrets are built from existing files so nothing is duplicated or committed.
- Why `imagePullPolicy: IfNotPresent` + `kind load` are needed for locally-built images.
- Why the HTTP Ingress on one host makes the Grafana embed work with no certificate step.
- Why training (Docker-out-of-Docker) was scoped out and what the k8s-native replacement is.

---

### Next up — Phase 16: Cloud

Take this to a free cloud so it's a live, shareable URL: **Track B** (quick — Streamlit Cloud
frontend + a hosted backend) first, then **Track A** (k3s on Oracle Always Free — real Kubernetes in
the cloud), adding real TLS and swapping the Grafana embed origin to the cloud host.
