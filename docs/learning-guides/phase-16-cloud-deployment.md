# Phase 16 — Cloud: the finale (a live, public URL)

> **Goal of this phase:** put the project on the public internet so a recruiter can click a link and
> use it — no install, no local Docker. We do it in two tracks: **Track B** (quick) gets a live demo
> up today on a free host; **Track A** (later) runs *real* Kubernetes in the cloud. This guide covers
> **Track B**, done as a **single Hugging Face Docker Space**, and previews Track A.

This is the last phase. Everything before it built the machine; this phase plugs it into a wall
socket the world can reach.

---

## 16.1 The two tracks, and why

| | Track B (this guide) | Track A (later) |
|---|---|---|
| Host | Hugging Face **Docker Space** (free) | **k3s** on Oracle Cloud Always Free (free) |
| What runs | backend + Streamlit in **one container** | full k8s: serving + monitoring, real Ingress |
| Scope | predict + explain | predict + explain + monitoring |
| Effort | ~30 min | a few hours (VM, DNS, TLS) |
| Point | a shareable URL **now** | show cloud-native ops on a real node |

Track B is deliberately the *quick win*: one free URL that stays up, so the project stops being
"clone it and run docker compose" and becomes "here's the link."

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

## 16.8 Track A preview — real Kubernetes in the cloud

Track A takes the Phase-15 manifests to a free cloud VM:

1. **Oracle Cloud Always Free** ARM VM (up to 4 cores / 24 GB) → install **k3s** (a tiny, single-node
   Kubernetes).
2. Push the images to a registry (GHCR/Docker Hub) so the cluster can pull them (no more
   `kind load`).
3. Apply the `k8s/` manifests; point a free domain (DuckDNS) at the VM.
4. Put **real TLS** in front (cert-manager + Let's Encrypt), then swap the Grafana embed origin and
   the Ingress host from `asp.local` to the cloud domain — the HTTP-on-one-host reasoning from
   Phase 15 §15.4 now runs on HTTPS on a real host.

That gives a public URL backed by *actual* Kubernetes with monitoring — the full stack, live.

## 16.9 Phase 16 checkpoint

You understand Phase 16 when you can explain:

- Why Streamlit Community Cloud alone can't host this, and why a single Docker Space (two processes,
  two ports, only 7860 public) is the quick answer.
- How the same env-driven config runs locally and in the cloud with no code change, and why the
  DagsHub token had to be rotated before going public.
- Why a `user`-role demo login yields predict + explain with no new gating code.
- What Track B leaves out (monitoring, training) and why those belong to Track A.
- The Track A path: k3s on a free VM, images from a registry, real TLS, cloud host swapped in.

---

*This is the final phase. The project now spans data → training → registry → drift-gated promotion →
API → GUI → monitoring → Kubernetes → a live public URL.*
