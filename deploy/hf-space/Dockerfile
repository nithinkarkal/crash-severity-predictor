# ---------------------------------------------------------------------------
# Hugging Face Space — single container running BOTH the FastAPI backend
# (internal, 127.0.0.1:8000) and the Streamlit GUI (public, 0.0.0.0:7860).
#
# Phase 16 / Track B: one free public URL for a recruiter-facing demo.
# Scope: predict + explain only (Monitoring/Training are hidden for the
# demo `user` role). The model is loaded at startup from the MLflow registry
# on DagsHub, using secrets injected as HF Space environment variables.
#
# HF Docker Spaces run the container as a non-root user with UID 1000, so we
# create that user and keep everything it writes inside its home directory.
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# uv for fast, locked installs
RUN pip install --no-cache-dir uv

# Non-root user expected by Hugging Face Spaces (UID 1000)
RUN useradd -m -u 1000 user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONPATH=/home/user/app \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/home/user/app/.venv \
    MPLCONFIGDIR=/home/user/.cache/matplotlib \
    # Frontend talks to the backend inside the same container
    BACKEND_URL=http://127.0.0.1:8000 \
    # Cloud demo flags (predict + explain only; demo creds shown on login).
    # DEMO_PASSWORD is intentionally NOT set here (avoids a build-time secret
    # warning) — the frontend defaults it to "demo1234"; override via an HF
    # Space variable if you change the demo password.
    CLOUD_DEMO=1 \
    DEMO_USERNAME=demo

WORKDIR /home/user/app

# --- dependencies (backend + training runtime + frontend), from the lock file
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --group backend --group training --group frontend

# --- application code
COPY common ./common
COPY services ./services
COPY .streamlit ./.streamlit
COPY deploy/hf-space/start.sh ./start.sh

# runtime folders the backend expects + make everything writable by UID 1000
RUN chmod +x ./start.sh \
    && mkdir -p data/processed artifacts/models artifacts/metrics artifacts/reports \
    && chown -R user:user /home/user

USER user

# HF routes public traffic to this port (must match app_port in README front-matter)
EXPOSE 7860

CMD ["./start.sh"]
