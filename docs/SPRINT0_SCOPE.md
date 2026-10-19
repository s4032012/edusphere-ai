# Phạm vi Sprint 0 và đối chiếu report

Sprint 0 xây nền kỹ thuật để phát triển Phase 1 với dữ liệu giả lập. Report sản phẩm v1.0 mô tả toàn bộ bốn phase và 320 chức năng; tài liệu Technical Foundation v2.0 trong folder chốt phạm vi Sprint 0 cụ thể hơn. Các module điểm, chuyên cần, nhắn tin, bài tập, AI và platform administration không thuộc phần triển khai Sprint 0.

| Yêu cầu nguồn | Hiện thực Sprint 0 | Phần tiếp theo |
| --- | --- | --- |
| Report §5 IAM, §12 AUTH-01/IAM-02/SIS-03 | Membership có hiệu lực, tenant header, queryset theo assignment/guardian/self, kiểm thử âm | Field/action policy cho điểm, workflow và approval |
| Report §6 modular monolith | Django identity/schools/academics; React web; ba Expo app riêng theo Foundation v2 | Worker/outbox khi triển khai nghiệp vụ bất đồng bộ |
| Report §6.4 dữ liệu nền | Account, Tenant, Membership, AcademicYear, Subject, Classroom, Student, Enrollment, TeacherAssignment, GuardianLink, StudentAccount, AuditEvent | Term, grade/version/amendment, attendance, messaging và AI lineage |
| Report §9 UI states | Login, role mismatch, chọn trường, roster, loading/error, logout/expiry; Platform Console preview công khai | Sáu flow nghiệp vụ cần prototype và UAT với người dùng |
| Foundation G-01/G-02/G-07 | Compose, migrations versioned, pnpm lockfile, CI PostgreSQL, typecheck/build | Kết quả thực thi xem VERIFY.md |
| Foundation G-08/G-10 | Đề xuất auth và cấu hình CI trong repository | Chủ dự án phê duyệt auth; remote CI và branch protection cần repository GitHub |

## Quyền hiện thực cho roster

| Role | Đọc học sinh/lớp | Tạo hồ sơ, lớp, phân công, liên kết |
| --- | --- | --- |
| SCHOOL_ADMIN | Trong trường đang là thành viên | Có, kiểm tra tenant, ghi audit |
| PRINCIPAL / VICE_PRINCIPAL / ACADEMIC_AFFAIRS | Trong trường đang là thành viên | Không |
| HOMEROOM_TEACHER | Theo phân công chủ nhiệm hiệu lực | Không |
| SUBJECT_TEACHER | Theo phân công bộ môn hiệu lực; không trả ngày sinh | Không |
| PARENT | Con có liên kết được xác minh, còn hiệu lực và cho phép xem | Không |
| STUDENT | Hồ sơ gắn với chính tài khoản | Không |
| SUPPORT_STAFF / DEPARTMENT_HEAD | Mặc định không được xem roster nếu không kiêm role có quyền | Không |
| Platform operator / Django superuser | Không tự có quyền tenant | Không nếu không có SCHOOL_ADMIN membership |

Ma trận này chỉ áp dụng cho hồ sơ/roster. SCHOOL_ADMIN không được hiểu là có quyền sửa hoặc công bố điểm; API điểm chưa tồn tại. Role kiêm nhiệm được hợp nhất tại backend, frontend chỉ lọc ứng dụng phù hợp.

## Đối chiếu schema

Không có file Phase1 SQL trong folder được cung cấp. ORM và migrations là schema thực thi của Sprint 0; không tuyên bố đã đối chiếu với một schema SQL chưa có. Khóa ngoại tenant được kiểm tra ở API ghi; truy vấn đọc luôn tenant-scoped. Chưa có PostgreSQL RLS hay composite foreign keys đảm bảo tenant cho mọi đường ghi trực tiếp SQL; phải bổ sung trước import/bulk jobs ở Sprint 1.

## Quyết định auth cần chủ dự án chốt trước dữ liệu thật

Đề xuất OIDC Authorization Code + PKCE cho mobile và BFF/HttpOnly cookie cho web. Cần chọn nhà cung cấp, quản lý MFA cho quyền đặc biệt, thu hồi phiên, reset account, TLS và chính sách session. JWT demo 15 phút hiện tại chỉ phục vụ phát triển; logout xóa phiên ở client, chưa thu hồi JWT trên server. Refresh token từ endpoint demo không được lưu hoặc dùng bởi app.

## Backlog Sprint 1 theo thứ tự

1. Chốt schema Phase 1, academic year/term và tenant invariants cho API, bulk import, SQL; test đối soát migration.
2. Auth production, action/field permission, audit theo yêu cầu nghiệp vụ.
3. Academic structure và UI phân công có ngày hiệu lực, kiểm tra trùng và thu hồi.
4. Student/guardian CRUD + import preview, xác minh/thu hồi giám hộ và lịch sử chuyển lớp.
5. Thiết kế và UAT sáu flow trong report; sau đó mới triển khai gradebook/attendance/messaging theo backlog đã chốt.
6. EAS signing, identifiers chính thức, quan sát vận hành và quy trình triển khai/rollback.

Các quyết định của trường, pháp lý, vendor identity và account store vẫn cần người có thẩm quyền; mã nguồn không thay thế những phê duyệt đó.
