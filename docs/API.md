# API Sprint 0

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

Roster tối đa 200 là giới hạn prototype, chưa đủ cho vận hành cả trường. Pagination/search/export và UI ghi dữ liệu thuộc Sprint 1. `date_of_birth` nullable và bị bỏ khỏi response cho giáo viên bộ môn; không giả định mọi role có cùng projection.
