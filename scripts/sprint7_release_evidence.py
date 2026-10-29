#!/usr/bin/env python3
"""Validate recorded manual evidence; does not authenticate signatures or certify compliance."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess

REQUIRED = ('native_ios', 'native_android', 'journeys_ui', 'accessibility_network',
            'security_privacy', 'backup_restore_rollback', 'monitoring_alerts', 'school_uat')


def validate(data, *, commit, root):
    failures = []
    if data.get('commit') != commit:
        failures.append('evidence must reference current Git commit')
    if data.get('open_p0_p1') != 0 or type(data.get('open_p0_p1')) is not int:
        failures.append('P0/P1 issues must be reviewed and zero')
    for name in REQUIRED:
        item = data.get('gates', {}).get(name, {})
        if (item.get('status') != 'PASS' or not isinstance(item.get('reviewer'), str)
                or not item['reviewer'].strip() or not isinstance(item.get('reviewed_at'), str)
                or not item['reviewed_at'].strip()):
            failures.append(name+': missing PASS/reviewer/date')
            continue
        try:
            datetime.fromisoformat(item['reviewed_at'])
        except (TypeError, ValueError):
            failures.append(name+': review date must be ISO 8601')
        artifact = root / str(item.get('artifact', ''))
        if not artifact.resolve().is_relative_to(root.resolve()) or not artifact.is_file():
            failures.append(name+': evidence artifact missing or outside evidence folder')
        elif hashlib.sha256(artifact.read_bytes()).hexdigest() != item.get('sha256'):
            failures.append(name+': artifact digest mismatch')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.evidence.read_text())
        commit = subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
        if subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'], text=True).strip():
            raise ValueError('working tree must be clean; keep evidence outside repository')
        failures = validate(data, commit=commit, root=args.evidence.parent)
        if failures:
            raise ValueError('; '.join(failures))
    except (OSError, ValueError, TypeError, AttributeError, subprocess.CalledProcessError) as error:
        raise SystemExit('NO-GO: '+str(error)) from None
    print('PASS recorded manual evidence; reviewer identity/signature must be independently verified.')


if __name__ == '__main__':
    main()
