# Phase 5 — Containerization

> **Goal of this phase:** understand how the whole system is packaged and run as **Docker
> containers**. We'll read both Dockerfiles (backend and training), the `.dockerignore` files, and
> `docker-compose.yaml`, and see how all the loose ends from Phase 4 — the mounted Docker socket,
> the `HOST_DATA_DIR`/`HOST_ARTIFACTS_DIR` env vars, the `asp-network`, the `asp-training:latest`
> image — click into place.

Phases 3 and 4 gave us a training service and an API that run on your laptop. Phase 5 makes them
**portable and reproducible**: "it works on my machine" becomes "it works in *the* image,
everywhere."

---

## 5.1 What & Why — containers in one paragraph

A **Docker image** is a frozen, self-contained filesystem: a specific Python, the exact installed
packages, and your code, baked together. A **container** is a running instance of an image. The
value for ML: the environment that trained/served the model is captured *as an artifact*, so it
behaves identically on your laptop, a teammate's machine, CI, or a cloud server. No more "works
here, breaks there" from a stray package version.

This project builds **three images**, because (from Phase 0) the backend, training, and edge proxy
have very different needs:

| Image | Built from | Purpose | Key extra ingredient |
|-------|-----------|---------|----------------------|
| `asp-backend:latest` | `services/backend/Dockerfile.backend` | serve the API, and *launch* training | the **Docker CLI** + the mounted host **socket** |
| `asp-training:latest` | `services/training/Dockerfile.training` | run one training job, then exit | the heavy **training** dependency group |
| `asp-nginx:latest` | `infra/nginx/Dockerfile.nginx` | TLS reverse proxy + rate limiter in front of the API | the TLS **cert** + `nginx.conf` (see §5.5a) |

Keeping them separate means the always-running API image doesn't carry LightGBM/XGBoost/pandas it
never uses, the training image doesn't carry a web server, and the proxy stays a tiny hardened
front door. Smaller images, clearer responsibilities. (The `asp-nginx` image was added later — §5.5a.)

---

## 5.2 `.dockerignore` — what does *not* go into the image

Both services ship an identical `.dockerignore` (same idea as `.gitignore`, but for the Docker
"build context" — the files sent to the builder):

```
.git .gitignore .github          # version control
__pycache__ *.pyc .venv          # python caches + local virtualenv
.pytest_cache .mypy_cache .ruff_cache
notebooks htmlcov mlruns *.ipynb # dev-only stuff
**/tests/ **/test_*.py conftest.py   # tests are NOT needed at runtime
Dockerfile* .dockerignore docker-compose*.yml
*.md docs/                       # documentation
```

Two reasons this matters:

1. **Smaller, faster builds.** The builder doesn't copy your 6 GB local `.venv`, notebooks, or
   caches into the context. (Note it also excludes `data/` and `artifacts/` implicitly — those
   aren't copied in; they arrive at *run* time via volumes, see §5.5.)
2. **Cleaner, safer images.** Tests, docs, and dev tooling have no business in a production
   runtime image. Excluding `**/tests/` is why the Dockerfiles can `COPY services ./services`
   yet still ship a test-free image.

---

## 5.3 `Dockerfile.training` — the training image

Read it top to bottom; each line is a layer.

```dockerfile
FROM python:3.12-slim                    # small official Python 3.12 base
WORKDIR /app                             # all following paths are relative to /app

ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} appuser && \ # create a NON-root user...
    useradd  -u ${USER_ID} -g appuser -m appuser

RUN pip install --no-cache-dir uv        # install uv (via pip, deliberately — see note)

COPY pyproject.toml uv.lock ./           # copy ONLY dependency files first (layer caching!)
RUN uv sync --frozen --no-dev --group training   # install exactly the locked training deps

COPY common ./common                     # then copy source (changes more often than deps)
COPY services ./services

ENV PYTHONPATH=/app                      # so `import common...` / `services...` resolve
RUN mkdir -p data/processed artifacts/models artifacts/metrics artifacts/reports && \
    chown -R appuser:appuser /app        # give the non-root user ownership
USER appuser                             # drop root for the actual run

RUN ls -la /app/.venv/bin/python         # sanity check the venv exists
ENTRYPOINT ["/app/.venv/bin/python", "-m", "services.training.train"]   # train + evaluate, then exit
```

Four professional patterns to internalize here:

- **Copy dependencies *before* source — the layer-cache trick.** Docker caches each instruction as
  a layer and reuses it if nothing it depends on changed. By copying `pyproject.toml`/`uv.lock`
  and running `uv sync` *before* copying your code, you only re-install packages when
  *dependencies* change. Edit a `.py` file and rebuild → Docker reuses the (slow) dependency layer
  and only redoes the (fast) code copy. This one ordering choice can turn a 5-minute rebuild into
  5 seconds.
- **`uv sync --frozen --no-dev --group training`.** `--frozen` = install *exactly* what `uv.lock`
  pins (fail if the lock is out of date) → reproducible builds. `--no-dev` drops the dev group
  (no pytest/ruff/jupyter in the image). `--group training` pulls in *only* the ML libraries. This
  is the dependency-group design from Phase 0 paying off inside the image.
- **Run as a non-root user.** Creating `appuser` and `USER appuser` before running is a security
  baseline: if the container is ever compromised, the attacker isn't root. The `USER_ID`/`GROUP_ID`
  build args let the container user match the host user, which avoids permission clashes on the
  bind-mounted folders (the comment block records a real DVC "Permission denied" bug this solved).
- **`ENTRYPOINT` = "run one job then exit."** The training image isn't a server — it runs
  `services.training.train` (train → evaluate, from Phase 3) and stops. That's exactly what the
  backend's `docker run --rm asp-training:latest` (Phase 4) wants: a one-shot task container.

The comments in the file are a mini changelog of real problems the team hit (uv download denied →
install via pip; DVC permission denied → non-root user + chown). That's honest, useful
documentation of *why* the Dockerfile looks the way it does.

---

## 5.4 `Dockerfile.backend` — the API image that can launch Docker

Same skeleton (slim base, uv, copy-deps-then-source, `PYTHONPATH`, runtime folders), with two big
differences.

**(a) It installs the Docker CLI.**

```dockerfile
USER root
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release \
    && pip install --no-cache-dir uv \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo "deb [...signed-by...] https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
         > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*
```

This adds Docker's official apt repo and installs **`docker-ce-cli`** — the Docker *client* only,
**not** the daemon. Remember from Phase 4: the backend needs to run `docker run asp-training...`.
For that it needs the `docker` command *inside* the container, but it will talk to the **host's**
daemon (via the socket, §5.5). This is the container-half of the "docker-out-of-docker" pattern.

**(b) It installs both `backend` *and* `training` groups.**

```dockerfile
RUN uv sync --frozen --no-dev --group backend --group training
```

Why would the API image need the training deps? It doesn't, for serving — but the comment history
and the shared code (`common/`, `services/`) mean it pulls both to be safe. (A stricter build
would install only `--group backend`; this is a pragmatic choice, and a spot you could tighten if
you wanted a leaner image.)

**(c) It's a long-running server, so `CMD` runs uvicorn:**

```dockerfile
EXPOSE 8000
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "services.backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`EXPOSE 8000` documents the port; `--host 0.0.0.0` makes the server reachable from outside the
container (binding to `127.0.0.1` would trap it inside). Note the contrast with training:
`ENTRYPOINT` + run-once for the job, `CMD` + serve-forever for the API.

> **`CMD` vs `ENTRYPOINT`:** both define what runs. Roughly, `ENTRYPOINT` sets a fixed executable
> (the container "is" that program — the training job), while `CMD` sets a default that's easy to
> override. The choice here reflects intent: training *is* one command; the backend has a default
> server command.

---

## 5.5 `docker-compose.yaml` — wiring the system together

A Dockerfile builds *one* image. **Compose** describes how to *run* one or more containers
together — their network, storage, environment, and lifecycle — in a single declarative file.
Here's the backend service, annotated:

```yaml
services:
  backend:
    build:
      context: .                                   # build from repo root...
      dockerfile: services/backend/Dockerfile.backend
      args:
        USER_ID: ${UID:-1000}                      # pass host user id (default 1000)
        GROUP_ID: ${GID:-1000}
    image: asp-backend:latest
    container_name: asp-backend
    expose:
      - "8000"                                     # internal-only now — NOT published to the host.
                                                   # Reach the API through Nginx (see §5.5a), not :8000.
    volumes:
      - ./data:/app/data                           # bind-mount host data  -> container
      - ./artifacts:/app/artifacts                 # bind-mount host artifacts -> container
      - /var/run/docker.sock:/var/run/docker.sock  # ← the host Docker socket (docker-out-of-docker)
    environment:
      HOST_DATA_DIR: ${HOST_PROJECT_ROOT}/data          # ABSOLUTE host paths...
      HOST_ARTIFACTS_DIR: ${HOST_PROJECT_ROOT}/artifacts # ...for the sibling training container
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    networks:
      - asp-network
```

Now every dangling reference from Phase 4 resolves. Read these five together:

1. **The mounted Docker socket** — `/var/run/docker.sock:/var/run/docker.sock`. This is the linchpin
   of docker-out-of-docker. The socket is how you talk to the Docker daemon; by mounting the
   *host's* socket into the backend container, `docker run` executed inside the backend is actually
   handled by the *host's* daemon, which spins up the training container as a **sibling** (not a
   child). That's why Phase 4's `training_service.py` could shell out to `docker run` at all.
2. **The `HOST_*` env vars** — `HOST_DATA_DIR`/`HOST_ARTIFACTS_DIR` are set to *absolute host
   paths* (`${HOST_PROJECT_ROOT}/data`). Phase 4 used exactly these to build the training
   container's bind mounts. They must be *host* paths because the host daemon (not the backend
   container) resolves them when it starts the sibling. This is the subtle gotcha the code's
   comments called out, now visible in context.
3. **The bind-mounted volumes** — `./data` and `./artifacts` are mounted in, so the model the
   training sibling writes to `/app/artifacts` lands in the *same host folder* the backend reads
   from. That shared folder is how a freshly trained model becomes visible to the running API
   (which then hot-reloads it, Phase 4). Mounting also means **you can retrain without rebuilding
   the image** — code is baked in, but data/models flow through the mount.
4. **The healthcheck** — periodically curls `/api/v1/health` (the endpoint from Phase 4). Docker
   uses the result to mark the container healthy/unhealthy; `start_period: 10s` gives the app time
   to boot before checks count. This is why `/health` reports model-loaded status — it's a real
   operational signal, not decoration.
5. **`restart: unless-stopped` + `networks: asp-network`** — auto-restart on crash, and join the
   named bridge network. The training sibling is launched with `--network asp-network` (Phase 4),
   so both containers share one network.

And the training service in compose:

```yaml
  training:
    build:
      context: .
      dockerfile: services/training/Dockerfile.training
      args: { USER_ID: ${UID}, GROUP_ID: ${GID} }
    image: asp-training:latest
    profiles: ["build-only"]                 # ← don't start on `compose up`; only build the image
    command: ["echo", "Training image built"]
    networks: [asp-network]

networks:
  asp-network:
    name: asp-network
    driver: bridge
```

The clever bit: **`profiles: ["build-only"]`**. The training image should *not* run as a
long-lived compose service — it's launched on demand by the backend. But compose still needs to
*build* `asp-training:latest` so the image exists when the backend calls `docker run`. Putting it
in a non-default profile means `docker compose up` **skips** it, while
`docker compose --profile build-only build` (or building explicitly) still produces the image. The
`command: echo ...` is a harmless no-op if it ever does start. This is a neat way to say "build
this image but don't run it as a service."

---

## 5.5a `asp-nginx` — the TLS reverse proxy + rate limiter

> **Added after the first draft** (PRs "security reverse proxy, rate limiting with nginx"). The
> backend is **no longer exposed to the host directly** (notice its `expose:` above, not `ports:`).
> Instead, a small **Nginx** container sits in front of it as the single entry point.

```yaml
  nginx:
    build: { context: ./infra/nginx, dockerfile: Dockerfile.nginx }
    image: asp-nginx:latest
    container_name: asp-nginx
    ports:
      - "8081:443"                       # the ONLY published port now (HTTPS)
    volumes:
      - ./infra/nginx/certs:/etc/nginx/certs:ro
    depends_on: [backend]
    networks: [asp-network]
```

**What Nginx does here, and why each part matters:**

1. **Single entry point + TLS termination.** All traffic enters at **`https://asp.local:8081`**
   (host `8081` → container `443`). Nginx holds the TLS certificate, decrypts HTTPS, and forwards
   plain HTTP to `asp-backend:8000` *inside* the private `asp-network`. Port 80 exists only to
   `return 301` redirect everyone to HTTPS. Because the backend now uses `expose` (not `ports`),
   **you can no longer reach it on `localhost:8000`** — everything goes through Nginx. That's the
   point: one hardened door instead of an open port.

2. **Rate limiting (abuse protection).** Nginx defines per-endpoint limits with `limit_req_zone`,
   keyed on client IP, returning **429** when exceeded:

   | Endpoint | Limit | Why |
   |----------|-------|-----|
   | `/api/v1/login` | 6 / min | slow down credential brute-forcing (pairs with Phase 4 auth) |
   | `/api/v1/train` | 1 / min | training is expensive + admin-only |
   | `/api/v1/predict` | 10 / sec | real serving throughput, but capped |
   | `/api/v1/health` | 20 / sec | cheap probe, generous |

3. **Security headers + body cap.** It adds headers like `Strict-Transport-Security`,
   `X-Content-Type-Options`, and a `Permissions-Policy`, and sets `client_max_body_size 10m` so
   oversized requests are rejected at the edge, before they reach the app.

**Dev certificate.** The cert is self-signed for local use — `infra/nginx/generate-dev-cert.sh`
creates `certs/nginx.{crt,key}` (git-ignored, never committed). Your browser will warn about the
self-signed cert; that's expected in development — proceed past the warning.

So the security model is now **two layers**: Nginx (TLS + rate limiting at the edge) in front of the
FastAPI **JWT auth** (identity + roles) from Phase 4.

---

## 5.6 The full runtime picture

```
        HOST MACHINE
        ┌──────────────────────────────────────────────────────────────────────┐
        │  Docker daemon  ◄───────────────────────────┐                          │
        │                                              │ docker run (via socket)  │
        │  ./data  ./artifacts   (host folders)        │                          │
        │      ▲          ▲                            │                          │
        │      │ bind     │ bind                       │                          │
        │  ┌───┴──────────┴────────────┐        ┌──────┴───────────────┐          │
        │  │ asp-backend (expose :8000) │        │ asp-training (--rm)  │          │
        │  │  uvicorn FastAPI + JWT     │        │  runs train→evaluate │          │
        │  │  docker CLI + mounted sock │═══════▶│  writes /app/artifacts│         │
        │  │  reads /app/artifacts      │ launches└──────────────────────┘         │
        │  └───────────▲────────────────┘                                          │
        │              │ HTTP (private asp-network)                                │
        │  ┌───────────┴────────────────┐                                          │
        │  │ asp-nginx  (:443)          │   TLS termination + rate limiting        │
        │  └───────────▲────────────────┘                                          │
        │       all three on  asp-network (bridge)                                 │
        └───────────────┼──────────────────────────────────────────────────────────┘
                        │ https://asp.local:8081   (ports 8081:443)
                       YOU  →  /api/v1/login → token → /predict , /health , /train
```

The story in one breath: you hit **Nginx** at `https://asp.local:8081`; it terminates TLS,
rate-limits, and forwards to the backend on the private network; the backend checks your **JWT**,
then serves predictions from the model in the shared `./artifacts` volume; when an admin
`POST /train`s, the backend uses the mounted socket to ask the host daemon to run the training image
as a sibling, which writes a new model back into the same volume, which the backend then hot-reloads.
The backend's own `:8000` is no longer reachable from the host — only through Nginx.

---

## 5.7 Reproduce it yourself

You need **Docker Desktop** running. From the repo root:

```bash
# 0) One-time: let your machine resolve asp.local, and make the dev TLS cert
#    add to /etc/hosts (Windows: C:\Windows\System32\drivers\etc\hosts):  127.0.0.1 asp.local
bash infra/nginx/generate-dev-cert.sh        # writes infra/nginx/certs/nginx.{crt,key}

# 1) Build the training image (it's build-only, so build it explicitly)
docker compose --profile build-only build

# 2) Build + start the whole stack (backend + nginx) in the background
docker compose up -d --build                 # starts asp-backend AND asp-nginx

# 3) Check it's alive — through Nginx over HTTPS (-k accepts the self-signed cert)
docker ps                                    # asp-backend "healthy" after ~10-40s; asp-nginx up
curl -k https://asp.local:8081/api/v1/health

# 4) Watch logs
docker compose logs -f backend nginx

# 5) Stop everything
docker compose down
```

> **Note the change from the first draft:** there's no more `curl http://localhost:8000`. The
> backend port isn't published — you reach it only via `https://asp.local:8081` through Nginx, and
> `/predict` + `/train` need a JWT (log in at `/api/v1/login` first, Phase 4 §4.3a).

**Set the host paths first.** The `HOST_*` env vars need your absolute project root. Create a
`.env` file next to `docker-compose.yaml`:

```bash
# .env  (compose auto-reads this)
HOST_PROJECT_ROOT=/absolute/path/to/accident-severity-predictor
UID=1000
GID=1000
```

**Expected output:** `docker ps` shows `asp-backend` with status `Up ... (healthy)`; the health
curl returns `{"status":"healthy","model_loaded":...}`. If `artifacts/` already contains a model
(from Phase 3 or `dvc pull`), `model_loaded` is `true` and you can `POST /api/v1/predict` exactly
as in Phase 4 — now served from inside a container.

> To exercise the full `/train` path you also need the training image built (step 1) and the socket
> mounted (it is, by the compose file). Then `POST /api/v1/train` will launch the sibling training
> container; follow `docker compose logs -f backend` to watch it happen.

**Windows note:** the Docker-socket mount (`/var/run/docker.sock`) and `UID/GID` user-matching are
Linux/Docker-Desktop conventions. On Windows they work through Docker Desktop's Linux backend
(WSL2); the `UID:-1000` defaults mean it still builds if those vars are unset.

---

## 5.8 Phase 5 checkpoint

You understand Phase 5 when you can explain:

- Why the project builds **two** images and what each contains (and why keeping them separate keeps
  each lean).
- What `.dockerignore` excludes and why tests/venv/notebooks shouldn't be in a runtime image.
- The **copy-deps-before-source** ordering and how Docker layer caching makes rebuilds fast.
- What `uv sync --frozen --no-dev --group ...` guarantees, and why running as a **non-root user**
  (with `USER_ID`/`GROUP_ID` args) matters for security and bind-mount permissions.
- `ENTRYPOINT` (run-once training) vs `CMD` (serve-forever backend), and why `--host 0.0.0.0`.
- **Docker-out-of-docker:** the mounted `/var/run/docker.sock` + `docker-ce-cli` in the backend let
  it launch the training image as a *sibling* via the host daemon — and why `HOST_DATA_DIR`/
  `HOST_ARTIFACTS_DIR` must be absolute *host* paths.
- How the shared `./data` and `./artifacts` bind mounts let a newly trained model reach the running
  API (which hot-reloads it), and why that means retraining needs no image rebuild.
- What the compose `healthcheck` does and how it ties back to Phase 4's `/health`.
- The `profiles: ["build-only"]` trick — build the training image but don't run it as a service.

---

### Next up — Phase 6: CI/CD

We move to `.github/workflows/` and read the four GitHub Actions pipelines — code quality
(Ruff/mypy), the test suite (pytest + coverage gate), the container build, and the orchestrating
`asp-ci.yaml`. We'll see how the local pre-commit gates from Phase 0 are re-enforced on the server,
how the workflows reuse each other, and how DagsHub/DVC secrets are handled in CI. Say **"Phase 6"**
when you're ready.
