# Phase 16 — Cloud: the finale (a live, public URL)

> **Goal of this phase:** put the project on the public internet so a recruiter can click a link and
> use it — no install, no local Docker. Two tracks: **Track B** packages the app as a single
> container for a quick host (Hugging Face / Cloud Run); **Track A** runs *real* Kubernetes in the
> cloud (k3s on a free Oracle VM) with monitoring and TLS. We built both; **Track A is the shipped,
> free public URL** (HF gated Docker Spaces behind PRO mid-project — see §16.1).

This is the last phase. Everything before it built the machine; this phase plugs it into a wall
socket the world can reach.

---

## 16.1 The two tracks, and why

| | Track B | Track A (the one we shipped) |
|---|---|---|
| Host | Hugging Face **Docker Space** | **k3s** on Oracle Cloud Always Free |
| What runs | backend + Streamlit in **one container** | full k8s: serving + monitoring, real Ingress + TLS |
| Scope | predict + explain | predict + explain + monitoring |
| Effort | ~30 min | a few hours (VM, DNS, TLS) |
| Point | a shareable URL fast | show cloud-native ops on a real node |

> **A note on Track B and "free".** When this project started, Hugging Face **Docker** Spaces ran
> free on the CPU-basic tier. In **July 2026 HF changed that** — creating Gradio *or* Docker Spaces
> now requires **PRO ($9/month)**; only **Static** Spaces stay free. The Track B container we built
> is real and works (it passed a full local smoke test), and it's **host-agnostic** — that same
> `deploy/hf-space/Dockerfile` runs on any Docker host (HF PRO, Google Cloud Run, a paid box). But
> for a genuinely **free** public URL we went with **Track A**, which is also the more impressive
> result: real Kubernetes with monitoring, on a free cloud VM. Track B stays in the repo as the
> quick/paid option.

## 16.2 The key constraint that shapes the design

Streamlit Community Cloud only runs **one Streamlit app** — it can't run our FastAPI backend. And the
frontend is useless without a backend to call. So on a single free host we have two options: host the
backend somewhere else (two services to manage), or **put both processes in one container**. For a
demo, one container is simpler and has one URL. Hugging Face **Docker Spaces** let us ship an
arbitrary `Dockerfile`, so that's the pick.

So the architecture for Track B is: **one image, two processes** —

```
HF Space container
├── FastAPI backend   → 127.0.0.1:8000   (internal only)
└── Streamlit GUI     → 0.0.0.0:7860     (HF proxies this to the public URL)
```

The frontend calls the backend over `localhost` inside the same container (`BACKEND_URL=
http://127.0.0.1:8000`). Nothing else is exposed.

## 16.3 One image, two processes

`deploy/hf-space/Dockerfile` installs the `backend`, `training`, and `frontend` dependency groups
(the backend needs the `training` group at *runtime* — mlflow, scikit-learn, shap — to load and
explain the model), copies `common/` + `services/` + `.streamlit/`, and runs `start.sh`.

`deploy/hf-space/start.sh` launches uvicorn in the background, polls `/api/v1/health` until the
backend is up (the model is pulled from the DagsHub registry at startup, which takes a few seconds),
then `exec`s Streamlit in the foreground so it's the container's main process.

**Two HF-specific gotchas, both handled in the Dockerfile:**

- **Non-root UID 1000.** HF runs the container as a non-root user with UID 1000. Anything the app
  writes at runtime (mlflow/dagshub caches, matplotlib config, the `artifacts/` folders the backend
  creates) must live somewhere that user can write. We create `useradd -u 1000 user`, set
  `HOME=/home/user`, put the app under `/home/user/app`, point `MPLCONFIGDIR` into the home cache,
  and `chown -R user:user /home/user` before switching to `USER user`.
- **`app_port` must match.** HF proxies public traffic to the port declared as `app_port` in the
  Space README front-matter. We set `app_port: 7860` and Streamlit listens on 7860.

## 16.4 Secrets are just environment variables

We never bake secrets into the image or commit them. Both the backend (`Settings(BaseSettings)`) and
the frontend read configuration from **environment variables** — pydantic-settings and DagsHub's SDK
both pick up `os.environ` automatically. HF injects everything you add under **Settings → Variables
and secrets** as env vars at runtime. So the *same code* that reads `.env.backend` locally reads HF
secrets in the cloud, with **zero code changes**.

What goes in the Space:

- **Secrets (masked):** `DAGSHUB_USER_TOKEN`, `JWT_SECRET_KEY`, `USER_USERNAME`,
  `USER_PASSWORD_HASH_B64`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH_B64`.
- **Variables (plain):** `DAGSHUB_REPO_OWNER`, `DAGSHUB_REPO_NAME`, `CLOUD_DEMO=1`, `DEMO_USERNAME`,
  `DEMO_PASSWORD`.

`deploy/hf-space/gen_secrets.py` prints all of these ready to paste (it generates a fresh
`JWT_SECRET_KEY` and the base64-bcrypt password hashes the backend expects).

**Rotate the DagsHub token first.** The token that was pasted in a chat during development is
considered burned — going public would make it internet-reachable. Regenerate it in DagsHub, use the
*new* one in the Space, and update your local `.env`.

## 16.5 Scoping the public demo to predict + explain

We don't want a public training button or an exposed Grafana on a free host. The trick is that we
already have **role-based access**: the demo account is the **`user`** role, and the sidebar +
`enforce_page_access` already hide Monitoring and Training from non-admins. So a user-role demo login
gives predict + explain **for free** — no feature flags needed for the gating itself.

The only cloud-specific UI touch is convenience: a `CLOUD_DEMO=1` flag (frontend setting) makes the
login page show and pre-fill the demo credentials, so a visitor just clicks **Login**. Locally
`CLOUD_DEMO` is unset, so the login page behaves exactly as before.

## 16.6 Reproduce it yourself

```powershell
# 1. Rotate the DagsHub token (DagsHub → Settings → Tokens), then update local .env

# 2. Generate the secret values to paste into HF
uv run python deploy/hf-space/gen_secrets.py            # copy the output

# 3. Create the Space on huggingface.co (New → Space → SDK: Docker → blank)
#    Then clone it and sync the curated files in:
git clone https://huggingface.co/spaces/<you>/crash-severity-predictor C:\hf\css
.\deploy\hf-space\sync_to_hf.ps1 -SpaceDir C:\hf\css
cd C:\hf\css ; git add -A ; git commit -m "deploy" ; git push

# 4. In the Space → Settings → Variables and secrets, paste the values from step 2
#    (put the NEW DagsHub token as DAGSHUB_USER_TOKEN). The Space rebuilds automatically.
```

When the build finishes, the Space URL serves the GUI. Log in with the demo credentials, run a
prediction, open the SHAP explanation. (First hit after the Space has slept takes a few seconds to
wake and to pull the model from the registry.)

**Optional local smoke test before pushing** (needs Docker Desktop):

```powershell
docker build -f deploy/hf-space/Dockerfile -t css-space .
docker run --rm -p 7860:7860 `
  -e DAGSHUB_USER_TOKEN=<new-token> -e DAGSHUB_REPO_OWNER=nithinkarkal `
  -e DAGSHUB_REPO_NAME=crash-severity-predictor -e JWT_SECRET_KEY=dev `
  -e USER_USERNAME=demo -e USER_PASSWORD_HASH_B64=<hash> `
  css-space
# open http://localhost:7860
```

## 16.7 What Track B leaves out (on purpose)

- **Monitoring (Prometheus/Grafana)** — stateful, multi-container, heavy for a free single-container
  host. It's the headline feature of **Track A**.
- **Training trigger** — long-running and it launches containers (Docker-out-of-Docker), which a
  managed Space won't do. Training stays a local/Airflow feature (same reason it was scoped out of
  Phase 15).

The served model is pulled from the **registry** at startup, so the demo needs no dataset volume and
no training — exactly why "serving from a registry" was worth building.

## 16.8 Track A — real Kubernetes in the cloud (what we shipped)

Track A takes the Phase-15 manifests to a free cloud VM and makes four cloud changes. The elegant
part: we **don't rewrite** the manifests — a **Kustomize overlay** (`k8s/cloud/`) reuses the base
(`k8s/base/` → the Phase-15 files) and patches only what differs.

**1. Images from a registry, not `kind load`.** On a real cluster there's no `kind load`; the node
pulls images. We cross-build the backend + frontend for **ARM64** (the free Oracle Ampere VM is
arm64, and a Windows PC is amd64, so `docker buildx --platform linux/arm64`) and push to **GHCR**.
The overlay's `images:` transformer rewrites `asp-backend` → `ghcr.io/nithinkarkal/asp-backend`, and
a patch sets `imagePullPolicy: Always` so rollouts re-pull. (`deploy/cloud/build_push.ps1`.)

**2. A tiny Kubernetes: k3s.** `deploy/cloud/setup_k3s.sh` installs **k3s** with Traefik disabled
(we keep ingress-nginx to match the project), then installs **ingress-nginx** and **cert-manager**.
k3s ships a default `local-path` StorageClass, so the Prometheus/Grafana PVCs just bind — no change.
Its built-in ServiceLB (klipper) binds host ports 80/443 to the ingress controller, so the VM's
public IP serves the cluster directly.

**3. A real host + TLS.** A free **DuckDNS** subdomain points at the VM's IP. The overlay patches the
Ingress host from `asp.local` to your domain, adds a `cert-manager.io/cluster-issuer` annotation and
a `tls:` block, and `k8s/cloud/cluster-issuer.yaml` defines **Let's Encrypt** issuers (HTTP-01 via
ingress-nginx). cert-manager then issues a browser-trusted certificate automatically.

**4. HTTPS everywhere for the embed.** Grafana's `root_url` and the frontend's `GRAFANA_URL` are
patched from `http://asp.local/grafana` to `https://<domain>/grafana`. The Phase-15 §15.4 reasoning
still holds — same host, ingress-nginx adds no `X-Frame-Options`, Grafana has `allow_embedding=true`
— only now it's HTTPS on a real domain, so the embed is clean *and* secure.

**Two firewalls.** Oracle VMs have a cloud-level Security List/NSG **and** the VM's own iptables
(Ubuntu images block everything but 22 by default). Both must open 80/443 — a classic first-timer
trap. `setup_k3s.sh` handles the VM iptables; the Security List you open in the Oracle Console.

**Token substitution.** The overlay carries `__DOMAIN__` / `__EMAIL__` tokens; `deploy/cloud/deploy.sh`
renders the overlay with `kubectl kustomize` and `sed`s the tokens in at apply time, so you set the
domain/email once as env vars instead of hand-editing YAML. The same script creates the
Secrets/ConfigMaps from your `.env*` and monitoring files exactly as the Phase-15 `deploy.ps1` did.

Full step-by-step: `deploy/cloud/DEPLOY.md`. End result: a public **HTTPS** URL backed by *actual*
Kubernetes with live monitoring — the whole stack, on a free cloud VM.

## 16.9 Phase 16 checkpoint

You understand Phase 16 when you can explain:

- Why a single Docker container (two processes, only 7860 public) is the quick Track-B answer, and
  why HF's July-2026 move to gate Docker Spaces behind PRO pushed the *free* path to Track A.
- How the same env-driven config runs locally and in the cloud with no code change, and why the
  DagsHub token had to be rotated before going public.
- Why a `user`-role demo login yields predict + explain with no new gating code.
- Why a **Kustomize overlay** (base + patches) beats copying the manifests, and what the four cloud
  patches change (registry images, ingress host, TLS, HTTPS Grafana URLs).
- Why the images must be **ARM64** for the Oracle Ampere VM, and how `buildx` cross-builds them.
- How k3s + ingress-nginx + cert-manager + DuckDNS produce a real HTTPS URL, and why **two**
  firewalls (Oracle Security List + VM iptables) must both open 80/443.

---

*This is the final phase. The project now spans data → training → registry → drift-gated promotion →
API → GUI → monitoring → Kubernetes → a live public URL.*
