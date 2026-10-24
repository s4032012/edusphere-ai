# Sprint 4 — Assignment & Homework

Integrated selectively onto accepted Sprint 3 (`32af54c`), preserving existing authentication, migrations, permission fixes and CI. The supplied PDF/diagrams describe the source kit; the implementation and verified results below supersede its unexecuted checks and known race conditions.

## Run locally

From the project root, with the existing demo backend running:

```bash
pnpm install --frozen-lockfile
docker compose exec backend python manage.py migrate --noinput
```

Run each desired app in a separate terminal:

```bash
pnpm dev:teacher-web   # http://127.0.0.1:5174
pnpm dev:teacher       # Expo 8081
pnpm dev:parent        # Expo 8082
pnpm dev:student       # Expo 8083
```

Restart all three Expo servers with `--clear` after upgrading to SDK 58 (required for current Expo Go). Teacher includes the native date/time picker (`@react-native-community/datetimepicker` 9.2.1, matched to Expo 58). Native development builds need rebuilding if this module was absent. Preserve working LAN API `.env` and Compose override settings; do not replace them with localhost for physical phones. Database startup applies committed migrations; no automatic `makemigrations`.

Demo password remains `DemoOnly!ChangeMe123`. `gvbm_a` creates a draft for their assigned class/subject, edits then publishes. `student_a` opens Homework, writes and submits. Teacher opens the roster, enters feedback/optional score and returns work. `parent_a` reloads Homework to view status and feedback without answer text. `gvcn_a` can view class progress but cannot manage/return tasks. Admin homework endpoints are read-only; no new Admin UI in this sprint.

Teacher Web and Teacher Mobile support draft editing, allow-late toggle, confirmations, due times and feedback/score. Teacher Mobile uses a native date/time picker. Forms respect server `can_manage`; 401 clears login. Components remount per token/tenant, discard late selection responses and guard duplicate writes. Student detects HTTP 409, retains the text for copying and requests an explicit reload before retrying. Submitted work can be resubmitted, not saved back as draft. The mobile student composer expects one linked student profile.

## Verification

```bash
bash scripts/verify_sprint4.sh
# Explicit PostgreSQL regression/concurrency checks:
docker compose exec -T backend python manage.py test apps.academics.tests apps.access.tests apps.attendance.tests apps.grades.tests apps.homework.tests
pnpm expo:doctor
pnpm build:mobile
```

`verify_sprint4.sh` uses SQLite by default unless PostgreSQL environment variables are provided; PostgreSQL concurrency cases are skipped on SQLite. `build:mobile` produces JS/Hermes bundles and assets for iOS/Android, not signed IPA/APK artifacts or real-device acceptance. CI runs PostgreSQL tests, migration/drift checks, contract tests, TypeScript, web builds, Expo dependency checks and mobile exports.

## Pilot limits

- Text submissions only: no uploads, AI, official gradebook writes or real notification delivery.
- Current enrollment/academic year policy; no historical assignment roster/name snapshot, transferred-student review workflow or reopen/return corrections.
- Up to 150 assignments per list, no pagination. Tenant-wide row locking favors correctness for one school over write throughput.
- Guardian/account activation, privacy/operations checks and real-device acceptance remain separate gates before using real student data.
