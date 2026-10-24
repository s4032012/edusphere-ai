# EduSphere AI — Sprint 4 REST API

**Header:** `Authorization: Bearer <JWT>`, `X-Tenant-ID: <school UUID>`. **All** endpoints are tenant-scoped. Base `/api/v1`.

| Method | Endpoint | Who | Behavior |
|---|---|---|---|
| GET | `/homework/` | Teacher, GVCN, School admin, student, verified parent | Scoped task list. Drafts only to author and school administration. |
| POST | `/homework/` | Assigned subject teacher | Create DRAFT; `classroom_id`, `subject_id`, `title`, `instructions`, `due_at` timezone-aware ISO8601, `allow_late`. |
| GET | `/homework/{task_id}/` | Authorized scoped role | Read task; parent/student only published or closed. |
| PATCH | `/homework/{task_id}/` | Original assigned subject teacher | Edit DRAFT only. |
| POST | `/homework/{task_id}/publish/` | Original assigned subject teacher | DRAFT → PUBLISHED; due date must still be in future. |
| POST | `/homework/{task_id}/close/` | Original assigned subject teacher | PUBLISHED → CLOSED; denies new submissions. |
| GET | `/homework/{task_id}/roster/` | Assigned teacher, GVCN, authorized admin | Student status, submission content restricted for GVCN. |
| GET | `/homework/students/{student_id}/` | Student, verified parent, assigned teacher, GVCN, admin | Published tasks for student's active class, return status and permission-filtered feedback. |
| GET | `/homework/{task_id}/my-submission/` | Student in class | Own submission and current task. |
| PUT | `/homework/{task_id}/my-submission/` | Student in class | `{content_text, action: save\|submit, expected_version?}`. On conflict: HTTP 409. |
| POST | `/homework/submissions/{submission_id}/return/` | Original assigned subject teacher | `{feedback,score?,expected_version}`; score decimal 0..10 step 0.1; only from SUBMITTED. |

## Examples

```json
POST /api/v1/homework/
{"classroom_id":"<UUID>","subject_id":"<UUID>","title":"Bài ôn tập số 1", "instructions":"Giải 3 phương trình", "due_at":"2026-11-01T17:00:00+07:00", "allow_late":false}
```

```json
PUT /api/v1/homework/<task-id>/my-submission/
{"content_text":"2x+5=15 → x=5", "action":"submit", "expected_version":1}
```

### Validation and security
- Role alone is insufficient: active teacher assignment and student-class enrollment/verified guardian relationship are checked.
- Teacher author + active assignment required to modify, publish, close and return work.
- Student identity derives from the logged-in account; supplied `student_id` cannot redirect a submission.
- A unique constraint allows **one current submission per (assignment, student)**. All homework writes acquire the same tenant row lock before reading state. Simultaneous first writes with version 0 produce one success and one HTTP 409; updates and returns also check the exact version.
- Parents and GVCN have read-only views. Parents and GVCN receive `content_text: null` through both overview and roster, including accounts with unrelated subject-teacher roles.
- `score` on HomeworkSubmission is **formative only**, not an official GradeEntry.
- Audit events and an outbox intent are written on mutations/return. Delivery service is not included.
- File upload, rubrics, bulk feedback, comments, per-student assignments, robust pagination and historical enrollment handling are **out of scope**.

## Implementation details

- `can_manage` is returned on every assignment, based on authorship + current subject assignment; the UI uses it to hide mutation controls. Backend checks remain authoritative.
- `expected_version` is a non-negative JSON integer (not boolean/string/float). First save/submit uses `0` (also default if omitted); later saves/resubmits require the version returned by GET. Return requires the teacher's observed version. HTTP 409 does not modify work or send notifications.
- Submission state is DRAFT → SUBMITTED → RETURNED. SUBMITTED may be submitted again while open and within deadline policy; `save` cannot downgrade it to DRAFT. RETURNED is immutable.
- Empty student drafts are allowed; submitted text must contain non-whitespace. Only strings, at most 20,000 characters. Feedback is at most 3,000 characters, plus optional decimal score 0..10 with at most one fractional digit.
- Due times must include timezone and be in the future on creation/edit/publication. Requests at the exact deadline are allowed. CLOSED prevents saves/resubmits even with `allow_late=true`; existing submitted work can still be returned.
- Active membership, academic year, enrollment, subject assignment and dated guardian academic permission are evaluated on every request. Current enrollment determines the roster; after a transfer/withdrawal, former-class tasks and notification intents disappear for pupil/parent and cannot be returned by the former teacher. Records remain in DB; historical roster/snapshots are deferred.
- Same-subject assigned colleagues may read published/closed rosters; only the author may mutate. Administration is read-only in this module.
- A HOMEWORK_RETURNED outbox intent is queued per linked student account/verified guardian. Payload contains assignment/student IDs only. `/notifications/` revalidates current enrollment and academic link/account before returning each event. No push/email delivery.
- List/overview cap: 150 assignments; notification cap: 100. Pagination and historical access are deferred.
