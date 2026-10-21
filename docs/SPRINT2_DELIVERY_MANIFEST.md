# Sprint 2 delivery manifest

Branch: `sprint-2/attendance-leave-management`, based on accepted Sprint 1 main.

- `backend/apps/attendance/`: four ORM models, initial migration, rules, ten URL patterns and 32 new tests.
- `backend/config/settings.py`, `urls.py`: app and route registration.
- `packages/api-client/src/index.ts`: typed attendance/leave/outbox methods; existing Sprint 1 contracts preserved.
- Teacher Web `AttendanceWeb.tsx`, Teacher Mobile `AttendanceManager.tsx`, Parent Mobile `LeaveAndAttendance.tsx`, mounted in existing authenticated shells.
- `.github/workflows/ci.yml` and `scripts/verify_sprint2.sh`: full backend regression coverage, client contracts, typechecks and builds.
- `docs/SPRINT2_API.md`, `SPRINT2_IMPLEMENTATION.md`, `SPRINT2_TEST_PLAN.md` and original kit diagrams.
- `docs/EduSphere_AI_Sprint2_Attendance_Leave_Management_v1.0.pdf`: user's original reference report, unchanged. Its starter-era QA statements do not describe the integrated code's verification.

No dependency upgrades, lockfile replacements, automatic makemigrations, new mobile app or real push provider. Existing Compose/LAN bindings are preserved. Local PostgreSQL migration applied successfully.

Verified: 92 PostgreSQL tests; SQLite 85 passed + 7 skips; 11 client tests; six typechecks; three web builds; Android/iOS exports for all three mobile apps. Manual acceptance pending.
