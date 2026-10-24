# Sprint 3 — Grade Management delivery

Integrated on `sprint-3/grade-management`, based on accepted Sprint 2 (PR #2 merged into main after user acceptance).

## Source

- `backend/apps/grades/`: GradeBook, Assessment, GradeEntry, GradeRevision; committed initial migration; authorization, calculations, atomic state changes and 40 grade tests.
- `backend/apps/attendance/views.py`: read publication/correction intents only when the recipient still has verified academic access.
- Admin Web `GradeAdministration`: configure books, confirm publication and approve/reject identified student/subject corrections.
- Teacher Web `GradesWeb`: create assessments, enter/lock grades, request revisions; homeroom view is read-only.
- Teacher Mobile `GradeManager`: create assessments and enter/lock grades.
- Parent/Student Mobile `GradeViewer`: published results and refresh; automatic permitted-student loading.
- Shared API contracts, CI and `scripts/verify_sprint3.sh`.
- Original report PDF and architecture diagrams are reference artifacts. The report's original unrun-test/migration statements are superseded by this integrated-source verification.

## Integration corrections

Preserved Sprint 2 dependencies, lockfile, committed migrations, auth expiry, SecureStore and LAN configuration. No automatic migration generation at server startup.

- All grade writes serialize per school using PostgreSQL tenant locks, avoiding duplicate publication/revision races and lock-order deadlocks. This trades throughput for consistency at pilot scale.
- Current assignment and school-year dates are enforced. An expired guardian link cannot expand a multi-role teacher's access to other subjects.
- Locked/published roster membership is read from saved entries, preserving records after enrollment closes; names still come from Student.
- Stale revision approval is rejected; stale requests may be rejected so a fresh request can be created.
- Published corrections create a separate deduplicated notification intent. Notification payloads contain IDs, not scores/reasons. Recipient permissions are rechecked at read time.
- Client screens reset on school/session changes, handle 401 logout, guard duplicate writes, ignore outdated book loads and save current inputs before locking.

## Verification

PostgreSQL: 132/132 passed. SQLite: 119 passed, 13 PostgreSQL-only concurrency tests skipped. Migration applied; no schema drift. Client: 14 contracts passed; six app typechecks, three web production builds and all three Android/iOS bundle exports passed. Expo compatibility check passed for all three apps.

Manual web/mobile acceptance remains pending; signed APK/IPA, real-device runtime, legal certification and production rollout are not claimed. See [acceptance steps](SPRINT3_ACCEPTANCE.md).
