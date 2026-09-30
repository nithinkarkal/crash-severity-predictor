# Track A — real Kubernetes in the cloud (k3s on Oracle Always Free)

A public **HTTPS** URL backed by actual Kubernetes: backend + frontend + Prometheus +
Grafana + node-exporter, behind ingress-nginx with a Let's Encrypt certificate.
Concepts & rationale: `docs/learning-guides/phase-16-cloud-deployment.md`.

Registry: **GHCR** · Domain: **DuckDNS** · VM: **Oracle Ampere A1 (ARM64)**.

---

## Files
- `build_push.ps1` — cross-build backend+frontend for **arm64**, push to GHCR (run on Windows)
- `setup_k3s.sh` — one-time cluster bootstrap on the VM (k3s + ingress-nginx + cert-manager + firewall)
- `deploy.sh` — deploy/redeploy the app on the VM (secrets, config, kustomize overlay, TLS)
- `../..//k8s/cloud/` — the Kustomize overlay (GHCR images, DuckDNS host, HTTPS Grafana, TLS)

---

## 0. Prerequisites (once)
- An **Oracle Cloud** account, and an **Ampere A1 (ARM)** VM created with **Ubuntu 22.04**,
  ~2–4 OCPU / 12–24 GB (all within Always Free). Note its **public IP**.
- A **GitHub PAT** (classic) with scope `write:packages` (for pushing images to GHCR).
- A **DuckDNS** subdomain (sign in at duckdns.org with GitHub → add a subdomain).

## 1. Point DuckDNS at the VM
On duckdns.org, set your subdomain's IP to the VM's public IP.
Verify from your PC: `nslookup <sub>.duckdns.org` returns that IP.

## 2. Build & push the ARM64 images (on your Windows PC)
```powershell
cd C:\Users\nithinkarkal\Documents\GitHub\crash-severity-predictor
$env:GHCR_TOKEN = "ghp_xxx"            # your PAT with write:packages
.\deploy\cloud\build_push.ps1
```
Then make both packages **public**: github.com/users/nithinkarkal/packages → each
(`asp-backend`, `asp-frontend`) → Package settings → Change visibility → Public.
(So the VM can pull without a login.)

## 3. Bootstrap the cluster (on the VM)
SSH in, get the code + your secrets onto the VM, then run the bootstrap:
```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/nithinkarkal/crash-severity-predictor.git
cd crash-severity-predictor
chmod +x deploy/cloud/*.sh
./deploy/cloud/setup_k3s.sh
```
Also open **80** and **443** (Ingress, TCP, source `0.0.0.0/0`) in the Oracle Console
under your VCN → Security List / NSG — the cloud firewall is **separate** from the VM's.

## 4. Copy your secrets + metrics to the VM
These are git-ignored, so `scp` them from your PC into the clone on the VM:
```powershell
# from your Windows PC (adjust user@VM_IP and the remote path)
scp .env .env.backend .env.grafana ubuntu@<VM_IP>:~/crash-severity-predictor/
scp -r artifacts\metrics ubuntu@<VM_IP>:~/crash-severity-predictor/artifacts\
```
Make sure `.env` on the VM has your **rotated** `DAGSHUB_USER_TOKEN`.

## 5. Deploy the app (on the VM)
```bash
export DOMAIN=<sub>.duckdns.org
export EMAIL=you@example.com
./deploy/cloud/deploy.sh
```
Watch it roll out. Certificate issuance takes ~1–2 min the first time:
```bash
kubectl get certificate -n asp -w      # wait for READY=True
```

## 6. Verify & share
- `https://<sub>.duckdns.org/` — GUI (login pre-filled demo / demo1234 if CLOUD_DEMO is on;
  otherwise your normal creds)
- `https://<sub>.duckdns.org/grafana/` — dashboards
- `https://<sub>.duckdns.org/api/v1/health` — API

Add the URL to your CV / LinkedIn Featured / repo README.

---

## Tips & gotchas
- **Test TLS with staging first** to avoid Let's Encrypt rate limits: edit the ingress
  annotation to `letsencrypt-staging`, confirm a cert is issued (browser will warn — that's
  expected for staging), then switch back to `letsencrypt-prod` and re-run `deploy.sh`.
- **`bad interpreter` on a .sh** → line endings: `sed -i 's/\r$//' deploy/cloud/*.sh`
  (the repo's `.gitattributes` forces LF, so a fresh clone should be fine).
- **Preview what will be applied**: `kubectl kustomize k8s/cloud` (renders the overlay).
- **Update after a code change**: re-run `build_push.ps1`, then on the VM
  `kubectl rollout restart deploy/backend deploy/frontend -n asp` (imagePullPolicy is Always).
- **Streamlit behind HTTPS**: the ingress sets long proxy timeouts for the websocket. If the
  GUI shows a connection error, check the ingress controller logs.
