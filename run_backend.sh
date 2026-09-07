#!/usr/bin/env bash
# One-shot backend bootstrap: install, train, seed, serve.
set -e
cd "$(dirname "$0")/backend"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
[ -f models/cognipath_models.joblib ] || python -m app.ml.train
[ -f cognipath.db ] || python -m app.database.seed
exec uvicorn app.main:app --reload --port 8000
