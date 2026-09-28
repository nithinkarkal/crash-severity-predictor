# DVC

##
git clone clone https://dagshub.com/Rackkoun/accident-severity-predictor.git
cd accident-severity-predictor

## Setup
cp .env.example .env

uv sync --all-groups

uv run dvc pull

dvc remote modify origin \
--local access_key_id <token>

dvc remote modify origin \
--local secret_access_key <token>
