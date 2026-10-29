#!/usr/bin/env bash
# Source/build success alone cannot authorize a school pilot.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# != 1 || "$1" == --* ]]; then
  echo 'NO-GO: provide reviewed evidence JSON. See docs/SPRINT7_ACCEPTANCE.md.' >&2
  echo 'For automated checks only: bash scripts/verify_sprint7.sh --full' >&2
  exit 2
fi
if [[ -x .venv/bin/python ]]; then sprint_python=.venv/bin/python; else sprint_python=python3; fi
# Reject absent/stale signoff before expensive automated checks.
"$sprint_python" scripts/sprint7_release_evidence.py "$1"
bash scripts/verify_sprint7.sh --full
echo 'PASS recorded evidence + automated gate. Deployment still follows the approved school runbook.'
