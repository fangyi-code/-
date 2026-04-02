#!/usr/bin/env bash
# Run after MySQL is up and .env matches (see scripts/mysql_reset_local_password.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -d .venv ]]; then
  echo "Create venv first: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi
# shellcheck source=/dev/null
source .venv/bin/activate
python manage.py migrate
python manage.py seed_feedsources
python manage.py generate_daily_report
echo "OK. Run: python manage.py runserver"
