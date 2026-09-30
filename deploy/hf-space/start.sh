#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Start both processes inside the Hugging Face Space container:
#   1. FastAPI backend on 127.0.0.1:8000 (internal only)
#   2. Streamlit GUI on 0.0.0.0:7860 (the public port HF proxies)
# Streamlit runs in the foreground (exec) so it is the container's main process.
# ---------------------------------------------------------------------------
set -euo pipefail

VENV=/home/user/app/.venv/bin

echo "[start] launching FastAPI backend on 127.0.0.1:8000 ..."
"${VENV}/python" -m uvicorn services.backend.src.main:app \
    --host 127.0.0.1 --port 8000 &

# Give the backend time to boot and pull the model from the DagsHub registry.
echo "[start] waiting for backend to accept connections ..."
for _ in $(seq 1 60); do
    if "${VENV}/python" - <<'PY' 2>/dev/null
import urllib.request
urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health", timeout=2)
PY
    then
        echo "[start] backend is up."
        break
    fi
    sleep 2
done

echo "[start] launching Streamlit GUI on 0.0.0.0:7860 ..."
exec "${VENV}/streamlit" run services/frontend/src/app.py \
    --server.port=7860 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false
