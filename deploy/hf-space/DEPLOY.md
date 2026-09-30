# Deploy the live demo — Hugging Face Docker Space (Track B)

A single free public URL running backend + Streamlit in one container.
Full explanation: `docs/learning-guides/phase-16-cloud-deployment.md`.

## Files here
- `Dockerfile` — one image, two processes (backend :8000 internal, Streamlit :7860 public)
- `start.sh` — launches both, waits for backend health, then runs Streamlit
- `README.md` — HF Space front-matter (SDK: docker, app_port: 7860). Becomes the Space's README.
- `.dockerignore` — keeps the build context lean
- `sync_to_hf.ps1` — copies the curated file set into a local clone of the Space
- `gen_secrets.py` — prints the env values (JWT key + bcrypt password hashes) to paste into HF

## Steps

**1. Rotate the DagsHub token (do this first).**
DagsHub → your profile → Settings → Tokens → revoke the old one, create a new one.
Update your local `.env` (`DAGSHUB_USER_TOKEN=...`).

**2. Generate the secret values.**
```powershell
uv run python deploy/hf-space/gen_secrets.py
```
Copy the printed block. Keep the admin password it prints somewhere safe (not public).

**3. Create the Space.**
huggingface.co → New → Space → Owner = you, Name = `crash-severity-predictor`,
SDK = **Docker**, template = **Blank**, visibility = Public. Create.

**4. Push the code into the Space.**
```powershell
git clone https://huggingface.co/spaces/<you>/crash-severity-predictor C:\hf\css
.\deploy\hf-space\sync_to_hf.ps1 -SpaceDir C:\hf\css
cd C:\hf\css
git add -A
git commit -m "deploy crash-severity-predictor"
git push
```
(HF asks for your username + an HF access token as the git password — make one at
huggingface.co → Settings → Access Tokens, `write` scope.)

**5. Add the secrets.**
Space → Settings → **Variables and secrets**. Add every line from step 2:
- Secrets (masked): `DAGSHUB_USER_TOKEN` (the NEW token), `JWT_SECRET_KEY`,
  `USER_USERNAME`, `USER_PASSWORD_HASH_B64`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH_B64`
- Variables (plain): `DAGSHUB_REPO_OWNER`, `DAGSHUB_REPO_NAME`, `CLOUD_DEMO=1`,
  `DEMO_USERNAME`, `DEMO_PASSWORD`

The Space rebuilds on each change. Watch **Logs** for `launching Streamlit GUI`.

**6. Try it.**
Open the Space URL → log in with the demo credentials (pre-filled) → run a prediction →
open the SHAP explanation. Add the URL to your CV / LinkedIn Featured / the repo README.

## Optional local smoke test (Docker Desktop)
```powershell
docker build -f deploy/hf-space/Dockerfile -t css-space .
docker run --rm -p 7860:7860 `
  -e DAGSHUB_USER_TOKEN=<new-token> `
  -e DAGSHUB_REPO_OWNER=nithinkarkal -e DAGSHUB_REPO_NAME=crash-severity-predictor `
  -e JWT_SECRET_KEY=dev -e USER_USERNAME=demo -e USER_PASSWORD_HASH_B64=<hash from gen_secrets> `
  css-space
# open http://localhost:7860
```
