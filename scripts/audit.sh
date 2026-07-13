#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "== pip-audit (requirements.txt) =="
pip-audit -r requirements.txt --strict

echo "== bandit (src/, etl/, app.py) =="
bandit -r src etl app.py
