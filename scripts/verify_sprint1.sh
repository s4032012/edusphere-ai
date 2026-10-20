#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -x .venv/bin/python ]]; then
  sprint_python=.venv/bin/python
else
  sprint_python=python3
fi
export DJANGO_DEBUG=1
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-sprint1-local-test-only-secret-at-least-32-chars}"
"$sprint_python" backend/manage.py check
"$sprint_python" backend/manage.py makemigrations --check --dry-run
"$sprint_python" backend/manage.py test apps.academics.tests apps.access.tests
pnpm test:contracts
pnpm typecheck
pnpm build:web
