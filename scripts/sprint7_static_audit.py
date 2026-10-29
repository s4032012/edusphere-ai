#!/usr/bin/env python3
"""Source safeguards only. Runtime evidence is collected separately."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

def audit(root=ROOT):
    def source(name):
        return (root/name).read_text(encoding='utf-8')
    ci = source('.github/workflows/ci.yml')
    domains = ('academics','access','attendance','grades','homework','communications','dashboard','regression')
    migrated = ('identity','schools','academics','attendance','grades','homework','communications')
    return {
        'startup_does_not_generate_migrations': 'manage.py makemigrations' not in source('compose.yaml'),
        'versioned_domain_migrations_present': all(list((root/f'backend/apps/{app}/migrations').glob('0*.py')) for app in migrated),
        'frozen_dependencies': (root/'pnpm-lock.yaml').is_file() and 'pnpm install --frozen-lockfile' in ci,
        'ci_postgresql_and_migration_drift': 'postgres:17-alpine' in ci and 'makemigrations --check --dry-run' in ci,
        'ci_all_domains': all(f'apps.{app}.tests' in ci for app in domains),
        'ci_web_and_mobile': all(command in ci for command in ('pnpm typecheck','pnpm build:web','pnpm expo:doctor','pnpm build:mobile')),
        'demo_debug_guard': 'if not settings.DEBUG' in source('backend/apps/identity/management/commands/seed_demo.py'),
        'separate_database_readiness': "path('readyz/', readyz)" in source('backend/config/urls.py') and 'SELECT 1' in source('backend/config/health.py'),
    }

if __name__ == '__main__':
    results = audit()
    for name, ok in results.items():
        print(('PASS' if ok else 'FAIL'), name)
    sys.exit(0 if all(results.values()) else 1)
