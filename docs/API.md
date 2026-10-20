# API Sprint 0 + Sprint 1

Base URL local: `http://127.0.0.1:8000`. Các endpoint có dấu `/` cuối. Ngoại trừ health và login, mọi endpoint cần `Authorization: Bearer <access>`. API theo trường cần thêm `X-Tenant-ID: <uuid>` lấy từ `/me/`.

| Method/path | Hành vi |
| --- | --- |
| GET `/healthz/` | Liveness tiến trình API; không phải kiểm tra DB |
| POST `/api/v1/auth/token/` | `{username,password}` → `{access,refresh}`; chỉ sử dụng access |
| GET `/api/v1/me/` | id, username, display_name, session_expires_at (Unix seconds), memberships còn hiệu lực |
| GET `/api/v1/students/` | Tối đa 200 hồ sơ đang active, có quyền; mảng sắp theo student_code |
| GET `/api/v1/students/{uuid}/` | Hồ sơ có quyền; ngoài phạm vi trả 404 |
| POST `/api/v1/students/` | School admin: student_code, full_name, date_of_birth tùy chọn |
| GET `/api/v1/classrooms/` | Tối đa 200 lớp theo phạm vi; mảng sắp theo code |
| POST `/api/v1/classrooms/` | School admin: code, grade_level (6–9), year UUID cùng trường |
| POST `/api/v1/enrollments/` | School admin: student_id, classroom_id cùng trường; chặn khi đã có lớp hiệu lực |
| POST `/api/v1/teacher-assignments/` | School admin: teacher_id, classroom_id, kind HOMEROOM/SUBJECT; SUBJECT cần subject_id; role giáo viên phải khớp |
| POST `/api/v1/guardian-links/` | School admin: guardian_id, student_id, relation tùy chọn; luôn chưa verified |
| POST `/api/v1/guardian-links/{uuid}/verify/` | School admin: evidence_checked phải là boolean true; ghi người xác minh và audit |

401: thiếu/sai/hết hạn token. 400: thiếu tenant, payload sai, dữ liệu trùng. 403: thiếu quyền thao tác. 404: tenant sai/không có membership hoặc object ngoài phạm vi. 429: quá giới hạn anonymous requests. Tránh phụ thuộc nội dung message để xác định trạng thái; dùng HTTP code.

Roster tối đa 200 là giới hạn prototype, chưa đủ cho vận hành cả trường. UI quản trị đã có trong Sprint 1; pagination/search phía server và export còn hoãn. `date_of_birth` nullable và bị bỏ khỏi response cho giáo viên bộ môn; không giả định mọi role có cùng projection.


## Sprint 1 administrative endpoints

All paths below start with `/api/v1/` and require token + tenant. All writes require `SCHOOL_ADMIN`. History, dashboard, guardian accounts and audit reads also require `SCHOOL_ADMIN`. Year/subject reads allow staff roles; staff reads allow admin, principal, vice-principal, academic affairs and department head.

| Method/path | Payload / behavior |
| --- | --- |
| GET `admin/dashboard/` | Counts scoped to tenant; active relationships respect school-year dates |
| GET/POST `academic-years/` | label, starts_on, ends_on; start < end; list cap 100 |
| GET/POST `subjects/` | code, name; list cap 200 |
| GET/POST `staff/` | username, display_name, role, optional email; list cap 300; unusable password on creation |
| PATCH `classrooms/{id}/` | code, grade_level, year; year cannot change once relationship history exists |
| PATCH `students/{id}/edit/` | student_code, full_name, date_of_birth |
| POST `students/{id}/archive/` | Empty body; requires no active enrollment flag; soft archive |
| GET `enrollments/list/` | Admin history, cap 500 |
| POST `enrollments/{id}/end/` | Empty body; immediate end + audit |
| GET `teacher-assignments/list/` | Admin history, cap 500 |
| POST `teacher-assignments/{id}/end/` | Empty body; immediate access revocation + audit |
| GET/POST `guardian-accounts/` | username, display_name; unusable password; list cap 300 |
| GET `guardian-links/list/` | Admin history, cap 300 |
| GET `audit-events/` | Latest 100 events, tenant-scoped |

New enrollments/assignments require a currently effective school year and get `ends_on` equal to year end. Concurrent enrollment and homeroom creation are serialized with PostgreSQL row locks. `is_active` on history rows denotes explicit closure, not a computed date-based permission; date scope is additionally enforced by authorization. New staff/guardian accounts report `invitation_status: NOT_SENT`; no invitation is actually sent. Duplicate username returns a generic unavailable error.
