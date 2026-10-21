# Sprint 2 - REST API contracts

All endpoints require Bearer JWT and `X-Tenant-ID`. All resource queries must be tenant-scoped. The access token is currently not refreshable by the UI; Sprint 2 remains a prototype.

| Method | Endpoint | Roles | Purpose |
|---|---|---|---|
| GET | `/api/v1/attendance/sessions/?date=YYYY-MM-DD` | School Admin, Academic Affairs, BGH (read), current Homeroom | Query class attendance sessions in allowed scope |
| POST | `/api/v1/attendance/sessions/` | School Admin, Academic Affairs, assigned Homeroom | Open or reuse class-day session; date max 7 days ago |
| GET | `/api/v1/attendance/sessions/{id}/` | School Admin, Academic Affairs, BGH (read), assigned Homeroom | Draft enrollment roster / published record roster, saved marks, derived leave status |
| PUT | `/api/v1/attendance/sessions/{id}/records/` | School Admin, Academic Affairs, assigned Homeroom | Partial batch upsert in DRAFT only |
| POST | `/api/v1/attendance/sessions/{id}/submit/` | School Admin, Academic Affairs, assigned Homeroom | Submit only with complete roster |
| POST | `/api/v1/attendance/sessions/{id}/lock/` | School Admin | Lock SUBMITTED roll call |
| GET | `/api/v1/attendance/students/{id}/` | School authorized, current Homeroom, verified Guardian (with academic visibility), own student | Published history; `effective_status` derived |
| GET | `/api/v1/leave-requests/?student_id={id}` | School authorized, current Homeroom, verified Guardian | Own submissions for parent; current student scope for reviewer |
| POST | `/api/v1/leave-requests/` | Verified Guardian | Apply for 1-14 days, within -7/+90 days |
| POST | `/api/v1/leave-requests/{id}/decision/` | Assigned Homeroom, School Admin, Academic Affairs | Approve/reject pending leave |
| POST | `/api/v1/leave-requests/{id}/withdraw/` | Original verified Guardian | Withdraw pending request only |
| GET | `/api/v1/notifications/` | Authenticated own account | Queued intents with current verified academic access; no delivery yet |

## Example 1: Create daily session

```http
POST /api/v1/attendance/sessions/
Authorization: Bearer <access-token>
X-Tenant-ID: <school-uuid>
Content-Type: application/json

{"classroom_id":"<class-uuid>","attendance_date":"2026-10-21"}
```

## Example 2: Save roll call

```http
PUT /api/v1/attendance/sessions/<session-uuid>/records/
Authorization: Bearer <access-token>
X-Tenant-ID: <school-uuid>
Content-Type: application/json

{"records":[{"student_id":"<student-uuid>","mark":"PRESENT"},{"student_id":"<student2-uuid>","mark":"ABSENT","note":"Chưa liên hệ được phụ huynh"}]}
```

Save operations are partial: teachers can mark students in several batches, but Submit requires all enrolled students on the target date to be marked. Unmarked entries are **not** silently treated as present.

## Example 3: Parent submits leave

```http
POST /api/v1/leave-requests/
Authorization: Bearer <parent-access-token>
X-Tenant-ID: <school-uuid>
Content-Type: application/json

{"student_id":"<student-uuid>","from_date":"2026-10-21","through_date":"2026-10-22","reason":"Khám bệnh theo lịch"}
```

## Example 4: Homeroom review

```http
POST /api/v1/leave-requests/<leave-id>/decision/
Authorization: Bearer <homeroom-access-token>
X-Tenant-ID: <school-uuid>
Content-Type: application/json

{"action":"approve","decision_note":"Đã xác nhận với phụ huynh"}
```

**Status semantics:** `PRESENT`, `ABSENT`, `LATE` are immutable physical attendance observations after submission. `EXCUSED_ABSENCE` is a **derived** presentation of `ABSENT` + accepted leave covering that date. The system does not auto-mark students present merely because a leave is approved.

**Errors:** 400 validation / illegal transitions; 401 missing or expired JWT; 403 insufficient role/relationship; 404 non-existent or foreign-tenant object. API does not promise paginated views beyond the pilot cap (200 rows).


## Integrated behavior

All Sprint 2 write transactions serialize per school on PostgreSQL to keep submit and leave decisions consistent. Session start is idempotent (201 new / 200 existing); repeated submit, lock, decision or withdrawal returns 400. Parent access requires an active verified guardian link with `can_view_academic=true`; loss of that permission hides both leave lists and notification intents. A parent's leave list excludes another guardian's submissions and sensitive reasons.

Published roster membership is read from AttendanceRecord; DRAFT still follows active enrollment. Lists cap after authorization: sessions 200, leaves 200, student history 120, queued notifications 100. No cursor pagination yet. Notification payloads contain IDs/status/date, not leave reasons. Delivery is not implemented.
