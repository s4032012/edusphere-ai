# Sprint 2 verification and acceptance

## Executed locally (2026-10-21)

| Check | Result |
| --- | --- |
| PostgreSQL 17 / Docker Python 3.13 | 92/92 passed |
| SQLite / Python 3.14 | 85 passed; 7 PostgreSQL-only tests skipped |
| API client contracts | 11/11 passed |
| TypeScript | Six app checks passed |
| React production builds | Admin, Teacher, Platform passed |
| Expo export | Teacher, Parent, Student: Android and iOS bundles passed |
| Migration | Applied attendance.0001_initial; drift check: no changes detected |

Sprint 2 adds 24 API regression tests, three pure rule tests and five PostgreSQL concurrency tests. Existing 60 Sprint 0/1 tests remain included. Coverage includes: role/tenant denial, invalid batch atomicity, complete-roster submission, post-submit immutability, guardian academic/link revocation, privacy between guardians, published roster after enrollment ends, audit rollback, overlapping leave requests, review/withdraw races, double submit, and submit/approve absence cancellation races.

Reproduce: `bash scripts/verify_sprint2.sh` (SQLite by default; honors DB environment). PostgreSQL: `docker compose exec -T backend python manage.py test apps.academics.tests apps.access.tests apps.attendance.tests`. Tests use a separate disposable test database, not the demo database.

## Manual acceptance pending

Browser control stalled while opening Safari; no visual/browser acceptance is claimed. Mobile bundle exports do not replace tests on a device.

Use only demo accounts and synthetic data:

1. Teacher Web (`pnpm dev:teacher-web`, http://127.0.0.1:5174): log in as `gvcn_a`. Open today's assigned class. All new entries must show unmarked.
2. Mark some pupils, save, reopen: preserve saved marks. Submit incomplete roster: clear error. Finish marking and submit: edits disabled, even after reopening.
3. Parent Mobile (`pnpm dev:parent`, `parent_a`): children load automatically. Draft attendance is hidden; published attendance appears after reload.
4. Parent sends today's leave request with a reason; a duplicate overlapping request is rejected. GVCN reloads pending requests and approves. Parent reloads: APPROVED; an ABSENT observation displays Nghỉ có phép without changing the stored mark.
5. Send a different pending leave and withdraw it; processed requests cannot be withdrawn. Another guardian must not see the reason or withdraw the request.
6. Teacher Mobile (`pnpm dev:teacher`) repeats save/submit/review. `gvbm_a` must not receive the daily-attendance controls and the API must reject those writes.
7. Admin locks a SUBMITTED session through the API; DRAFT lock and post-lock edits fail. Admin lock UI is deferred in this scope.
8. Repeat with tenant B; foreign tenant IDs must fail. Remove a guardian/assignment in the test setup and retry with the same token: rights disappear.
9. Logout, switch school, change class/day while requests are in flight; old rows must not populate the new context. Check expiry, errors/retry, keyboard, scrolling and small screens on iOS/Android.

No actual push is expected. Notifications endpoint returns only queued intents still authorized for the recipient; canceled absence intents are hidden. Production school policy, calendar, corrections, consent/evidence and operational readiness remain separate gates.

## CI compatibility follow-up (2026-10-22 local time)

The first GitHub run passed backend, client tests, typechecks and web builds, but Expo's remote version check required newer SDK 57 patch releases. Updated Expo to ~57.0.31 and Router to ~57.0.29 for all three apps, including the frozen lockfile. This is a patch update, not an SDK migration.
