#!/usr/bin/env bash
# Offline/source checks by default; --full also checks the running dev stack.
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in ''|--full) ;; *) echo 'Usage: bash scripts/verify_sprint7.sh [--full]' >&2; exit 2;; esac
if [[ -x .venv/bin/python ]]; then sprint_python=.venv/bin/python; else sprint_python=python3; fi
export PYTHONPATH="$PWD/backend"
"$sprint_python" -m compileall -q backend scripts
"$sprint_python" -m unittest apps.access.tests.test_policy apps.attendance.tests.test_rules apps.grades.tests.test_rules apps.homework.tests.test_rules apps.communications.tests.test_rules apps.dashboard.tests.test_rules
"$sprint_python" -m unittest discover -s scripts/tests -v
"$sprint_python" scripts/sprint7_static_audit.py
pnpm test:contracts
node scripts/check_native_text.mjs
node --test scripts/tests/native_text.test.mjs
if [[ "${1:-}" != --full ]]; then
  echo 'PASS source checks only. PostgreSQL/web/mobile/HTTP/recovery NOT RUN; use --full.'
  exit 0
fi
# Do not up/down/recreate the user's Compose stack (preserves LAN overrides).
docker compose exec -T backend python -c "import os; assert os.environ.get('DB_ENGINE') == 'postgres', 'PostgreSQL required'"
docker compose exec -T backend python manage.py check
docker compose exec -T backend python manage.py makemigrations --check --dry-run --noinput
docker compose exec -T backend python manage.py migrate --check
docker compose exec -T backend python manage.py test apps.academics.tests apps.access.tests apps.attendance.tests apps.grades.tests apps.homework.tests apps.communications.tests apps.dashboard.tests apps.regression.tests --noinput
pnpm install --frozen-lockfile
pnpm typecheck
pnpm build:web
pnpm expo:doctor
pnpm build:mobile
"$sprint_python" scripts/sprint7_smoke.py
docker compose exec -T backend python < scripts/sprint7_probe_drill.py
"$sprint_python" scripts/sprint7_recovery_drill.py
echo 'PASS automated checks only. Native device, privacy, operational monitoring and school UAT signoff remain separate.'
