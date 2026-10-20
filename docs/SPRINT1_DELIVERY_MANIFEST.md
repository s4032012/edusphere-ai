# Sprint 1 delivery manifest

Integrated into the existing Sprint 0 repository on branch `sprint-1/school-administration-core`.

- `apps/admin-web/src/App.tsx`, `style.css`: administration portal with dashboard and nine management sections.
- `packages/api-client/src/index.ts`: typed administrative resources and GET/POST/PATCH methods; preserved session contract and request invalidation helper.
- `backend/apps/access/sprint1_views.py`, `views.py`, `scopes.py`, `backend/config/urls.py`: administrative workflows, tenant isolation, date checks, transactional audit and concurrency guards.
- `backend/apps/academics/tests/test_sprint1.py`: 26 new integration tests.
- `backend/apps/academics/tests/test_sprint1_concurrency.py`: two PostgreSQL concurrency tests.
- `packages/api-client/tests/contracts.test.mjs`: nine contract tests total.
- `scripts/verify_sprint1.sh`: repeatable local verification.
- `docs/SPRINT1_IMPLEMENTATION.md`, `SPRINT1_TEST_PLAN.md`, `API.md`: scope, actual results and API reference.
- `docs/diagrams/sprint1_*.dot/png`: original kit diagrams.
- `docs/EduSphere_AI_Sprint1_School_Administration_Core_v1.0.pdf`: user's original reference report.

Preserved: four existing Django migration files, lockfile, dependency versions, Docker/LAN configuration, CI and all three separate mobile applications. No schema migration or dependency upgrade is required.

Automated verification: PostgreSQL 60/60, SQLite 58 passed + 2 PostgreSQL-only tests skipped, client contracts 9/9, six app typechecks and three web builds. Manual Admin acceptance remains pending. New accounts require a future activation flow; use only synthetic data.
