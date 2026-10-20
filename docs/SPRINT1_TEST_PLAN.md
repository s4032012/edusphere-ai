# Sprint 1 verification — 2026-10-20

## Executed checks

| Check | Result |
| --- | --- |
| Backend SQLite | 58 passed; 2 PostgreSQL-only concurrency tests skipped |
| Backend PostgreSQL 17 / Docker Python 3.13 | 60/60 passed, including two simultaneous-request tests |
| Migration drift | No changes detected |
| API client contracts | 9/9 passed |
| TypeScript | All six apps passed |
| Web production builds | Admin, Teacher and Platform passed |

Backend tests cover the Sprint 0 authorization contract plus all new administrative write role gates, cross-tenant lists and mutations, duplicate enrollment/assignment, expired years, immediate teacher access revocation, guardian verification, unusable account passwords, audit isolation and rollback. PostgreSQL tests submit simultaneous enrollments and homeroom assignments and require exactly one 201 and one 400.

Run `bash scripts/verify_sprint1.sh` for SQLite + client + TypeScript + web checks. Run `docker compose exec -T backend python manage.py test apps.academics.tests apps.access.tests` for PostgreSQL concurrency coverage. Tests create and destroy a separate test database; existing demo records are not modified.

## Manual acceptance still required

New Admin screens have not completed browser acceptance. Native Chrome automation was interrupted by concurrent user activity; no visual QA pass is claimed. Mobile source is unchanged; Sprint 0 user confirmation remains historical evidence only.

Use synthetic records and `admin_a` at http://localhost:5173:

1. Login; check dashboard, all ten navigation pages and school selection.
2. Create a current academic year, subject, class and student (DOB may be blank). Repeat a code: see a readable validation error without a duplicate row.
3. Create teacher and guardian accounts: show pending activation; they must not log in yet. Use existing demo teachers to test authenticated access.
4. Enroll the new pupil and assign an existing teacher to the new class. Teacher roster should include the pupil. End the assignment: the same teacher token must lose access immediately.
5. Create a guardian link: parent cannot see the new pupil until admin explicitly verifies it. This acknowledgement is demo-only evidence handling.
6. Inspect audit; refresh; confirm tenant isolation with `admin_b`. Login with teacher/parent on Admin must fail the role gate.
7. Logout/change school while loading: no previous school's rows return. Expired token returns to login.
8. Check keyboard focus, narrow viewport, table scrolling and error/retry states.

Student edit/archive and classroom edit are API-only. Archive requires ending active enrollment first. Server-side pagination/search, invitation activation, evidence upload and guardian revocation UI are deferred in the supplied scope.
