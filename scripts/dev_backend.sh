#!/usr/bin/env bash
set -euo pipefail
python -m uvicorn app.main:app --reload --app-dir backend/app

