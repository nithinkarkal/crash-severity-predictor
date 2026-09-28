.PHONY: init-project dvc-pull train-model dvc-push run-pipeline run-backend stop-backend rm-pycache


# 1. Run this once after cloning or pulling to install all dependencies locally
init-project:
	uv sync --all-groups

# 2. Fetch the current data and model versions from DagsHub
dvc-pull:
	uv run dvc pull

# 3. start backend
run-backend:
	docker compose up -d --build backend

# 4. stopp backend
stop-backend:
	docker compose down

# 5. DVC Push
dvc-push:
	uv run dvc push

# 6. Execute the entire end-to-end ML pipeline locally (using dvc.yaml)
run-pipeline:
	uv run dvc repro
	uv run dvc push

# extra or help func
rm-pycache:
	find . -regex '^.*\(__pycache__\|\.py[co]\)$' -delete
