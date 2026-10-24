# Sprint 3 — Grade Management REST API v1

**All endpoints require** `Authorization: Bearer <JWT>` + `X-Tenant-ID: <school-uuid>`. The backend checks active tenant membership and class/subject/guardian links for every operation. Field-based permissions are not delegated to frontend.

## Endpoints

| Method | Route | Roles | Behavior |
|---|---|---|---|
| GET | `/api/v1/gradebooks/` | Admin, academic affairs, leadership, teacher | Lists allowed books |
| POST | `/api/v1/gradebooks/` | Admin, academic affairs | Create a semester book with explicit mode and number of TX slots |
| GET | `/api/v1/gradebooks/{book_id}/` | Admin, leadership, authorized teacher | Teachers see own subject; GVCN sees published only |
| POST | `/api/v1/gradebooks/{book_id}/assessments/` | Assigned subject teacher, admin/academic affairs | Create `TX`, `GK` or `CK` column |
| PUT | `/api/v1/assessments/{id}/entries/` | Assigned subject teacher, admin/academic affairs | Atomic batch write while `DRAFT` |
| POST | `/api/v1/assessments/{id}/lock/` | Assigned subject teacher, admin/academic affairs | Reject incomplete roster |
| POST | `/api/v1/assessments/{id}/publish/` | Admin, academic affairs | After LOCKED, mark PUBLISHED; queue notifications |
| GET | `/api/v1/students/{student_id}/grades/` | Verified parent, self student, authorized staff | Published values only |
| POST | `/api/v1/grade-entries/{id}/revision-requests/` | Assigned subject teacher, admin/academic affairs | Request change to LOCKED/PUBLISHED grade |
| GET | `/api/v1/grade-revisions/` | Admin, academic affairs, subject teacher | Scoped list |
| POST | `/api/v1/grade-revisions/{id}/decision/` | Admin, academic affairs | Approve/reject using optimistic version |

## Examples

Create gradebook (`POST /api/v1/gradebooks/`):

```json
{"classroom_id":"<CLASSROOM_UUID>","subject_id":"<SUBJECT_UUID>","semester":"1","mode":"SCORE","regular_required":2}
```

Create assessment (`POST /api/v1/gradebooks/{book_id}/assessments/`):

```json
{"kind":"TX","slot":1,"title":"Kiểm tra thường xuyên 1"}
```

Save scores (`PUT /api/v1/assessments/{id}/entries/`):

```json
{"entries":[{"student_id":"<STUDENT_1_UUID>","score":"8.5"},{"student_id":"<STUDENT_2_UUID>","score":"7.0"}]}
```

For qualitative assessment use `{ "result": "PASS" }`, `FAIL`, or `EXEMPT` instead of score. `EXEMPT` can be submitted only by School Admin/Academic Affairs after off-system verification; it is excluded from automatic semester result in this prototype. No formal exemption-document workflow exists yet.

Request grade correction (`POST /api/v1/grade-entries/{entry_id}/revision-requests/`):

```json
{"score":"8.0","reason":"Đối chiếu phát hiện nhập nhầm điểm kiểm tra"}
```

Approve (`POST /api/v1/grade-revisions/{revision_id}/decision/`):

```json
{"action":"approve","decision_note":"Đã xác minh bài kiểm tra gốc"}
```

## Error rules

- `400`: invalid score, wrong assessment slot/mode, duplicate score entry, incomplete roster, invalid transition, or stale correction version.
- `403`: member without required class/subject operation permissions.
- `404`: tenant not found / object not in member's tenant / child not visible.
- `401`: missing/invalid JWT.
- Invalid payload never partially writes a batch (DB atomic).

**Caution:** Dynamic roster is used for pilot; production must snapshot roster at assessment creation, implement enrollment transition policies, immutable result logs, pagination, formal policy versions, and digitally signed school records where legally required. No online exams/e-schoolbook signature supported here.


## Integrated response and consistency behavior

`GET gradebooks/{id}/` includes `can_edit` for presentation; the server still enforces every write. For DRAFT, entry rows follow current enrollment. LOCKED/PUBLISHED rows follow saved entry membership, including students whose enrollment later ended.

Student endpoint returns only books with at least one published entry for that student; empty unpublished book configuration is omitted. Gradebook scope checks current school-year dates. Guardian checks include validity dates even for users holding multiple roles.

Revision lists include student_name, classroom_code, subject_name, assessment_title, old_result and decision_note so approvals can identify the exact record. Approval requires the original entry version; rejection is permitted for stale requests. Approval of a published correction creates `GRADE_CORRECTED`; publication creates `GRADE_PUBLISHED`. Outbox payloads contain only identifiers. Notifications are not delivered and are hidden when guardian academic access expires/revokes.

All grade writes use the same per-school transaction lock as Sprint 2. Concurrent duplicates return one success and one 400. Write/audit failure rolls back the transaction. This is pilot consistency, not PostgreSQL RLS or a complete immutable academic-history system.
