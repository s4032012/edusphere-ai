# EduSphere AI - Sprint 2: Attendance & Leave Requests

**Version:** v1.0, 21 October 2026. **Pilot:** one Vietnamese lower-secondary school (THCS). **Status:** integrated implementation; automated verification passed; manual acceptance pending. Synthetic data only.

## Goal and scope
- Homeroom Teacher marks `PRESENT/ABSENT/LATE` for class-days and submits only completed rosters.
- Parent with verified `GuardianLink` submits/withdraws leave for own child and reads approved published attendance.
- Homeroom Teacher or delegated academic affairs/admin reviews leave; school admin locks attendance.
- Discrete Outbox events are enqueued, **not delivered** as push/SMS.
- AuditEvent records create/save/submit/lock/apply/decision/withdraw operations.
- Both Teacher Web and Teacher Mobile contain the attendance UI; Parent Mobile contains the parent flow.

## Intentional exclusions
- Per-period / subject-teacher attendance (requires teaching timetable sessions and school policy).
- Reopening or editing submitted/locked attendance (requires separately authorized correction workflow and immutable revision history).
- Offline operation/sync, camera attendance, biometric check-ins, school holidays.
- Teacher notifications of incoming leave, real push or email providers, automatic reconciliation with state registry.
- Medical document attachments (require special handling of sensitive student data).
- Production data and production usage.

## Workflow / status machines
- Attendance: DRAFT -> SUBMITTED -> LOCKED. No edits after SUBMITTED.
- Leave: PENDING -> APPROVED, REJECTED, or WITHDRAWN; no repeated transitions.
- Approved leave does not mutate an original `ABSENT`. An effective UI state of `EXCUSED_ABSENCE` is derived.
- Submitting a session with non-excused absent students creates `UNEXCUSED_ABSENCE` outbox rows for verified guardians; late leave approval cancels queued notices for that student/date and creates `LEAVE_DECIDED` notification.

## Authorization rules
- A `HOMEROOM_TEACHER` membership alone is not enough; the user must have a currently valid **assignment** to the classroom.
- The class, student, enrollment, link, attendance, and leave all belong to the same tenant; all queries require `X-Tenant-ID`.
- Subject Teachers cannot create daily class roll call or approve leave requests, even if teaching the same pupils.
- Parent can submit leave only for a verified linked child. Only creator can withdraw a pending request.
- School Admin and Academic Affairs may review leave; Principal/Vice Principal can read but not decide by default.
- DRAFT roster uses current active enrollments valid on the attendance date. Published roster membership comes from saved records, so ending enrollment does not remove published pupils. Names are not immutable snapshots; draft transfer/correction policy still needs review.
- Parent leave lists contain only their own submissions; another guardian cannot read the submitted reason. Academic permission and current verified links are required for parent flows and notifications.
- GVCN must also be within the current academic year. Leave dates cannot extend beyond the enrolled classroom year.

## Product UX decisions
- No auto-mark-all-present: every pupil's status must be explicitly chosen; incomplete roll call cannot be submitted.
- Parent sees school-reported attendance only after SUBMITTED (or LOCKED).
- Parent provides dates and a reason; leave form validates again in backend.
- UX currently uses simple date text fields in mobile prototype; replace with accessible picker and localized errors during hardening.
- Separate standalone apps retained: `teacher-mobile` and `parent-mobile` get new screens; `student-mobile` unchanged.

## Data model
Four additional models in `apps/attendance/models.py`:
- `AttendanceSession` per (tenant, classroom, date), with state and timestamps.
- `AttendanceRecord` unique (session,student), mark, note, updated_by.
- `LeaveRequest` student, guardian, date range, reason, state, reviewer and decision.
- `NotificationOutbox` recipient, event, dedupe key, queued/canceled delivery state.

Business logic is in `rules.py`; endpoint and relationship checks in `views.py`. React apps use typed `createAttendanceApi()` in shared package.

## Running the project locally
From repo root:

```bash
corepack enable
docker compose up --build -d
# Existing committed migrations are applied at startup; never generate them automatically:
docker compose exec backend python manage.py seed_demo
# Install Node dependencies and run web:
pnpm install --frozen-lockfile
pnpm dev:teacher-web
# Or mobile:
cd apps/teacher-mobile && pnpm start
```

`seed_demo` creates synthetic demo schools, homeroom/subject teachers, guardians, and students. Teacher `gvcn_a`, parent `parent_a`, demo password described in root README. For mobile devices ensure `EXPO_PUBLIC_API_URL` is reachable from the device LAN and keep real data out of this setup.

Run: `bash scripts/verify_sprint2.sh`.

## Sprint 3 prerequisite decisions
- Academic calendar and class-day vs per-period attendance policy.
- Policy for staff-managed corrections after submission and multi-level approval.
- Data retention/guardian verification and school legal review for minors.
- Real notification design and secure push token storage.

## Integration details and verification

The original starter kit was selectively integrated into the verified Sprint 1 branch. Existing migrations, session expiry handling, SecureStore and LAN configuration remain intact. Expo/Router were updated within SDK 57 to ~57.0.31/~57.0.29 (with the pnpm lockfile) after the remote compatibility check required these new patches. `attendance/migrations/0001_initial.py` adds four tables; it was applied to the local PostgreSQL development database.

Sprint 2 write transactions lock the tenant row before individual session/leave rows. This serializes writes per school for the pilot and prevents submit/approval races from leaving a false queued absence. This is a deliberate throughput tradeoff; it is not a replacement for future worker delivery locking or database-wide tenant constraints.

UI changes preserve token-expiry logout and remount module state on school/session change. Save/submit controls prevent duplicate clicks. Submit saves the current marks first and rejects an incomplete roster; no student is automatically marked present. Class/date changes clear the open session. Parent has a reload action and automatically loads permitted children after sign-in.

Executed: PostgreSQL 92/92; SQLite 85 passed and 7 PostgreSQL-only tests skipped; 11 API client contracts; six app typechecks; three web production builds; all three Expo apps exported Android/iOS bundles. These exports are not signed APK/IPA files or device acceptance. See the test plan for the remaining manual checks.

School Admin lock is API-only as in the supplied scope. Notifications are database intents only; there is no delivery worker, push provider, or notification UI. Correction/reopening workflow, school calendar, activation and pagination remain deferred.
