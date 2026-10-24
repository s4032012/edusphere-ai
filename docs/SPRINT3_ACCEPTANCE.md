# Sprint 3 — Acceptance and regression gate

1. School Admin configures class + subject + semester + mode + 2/3/4 regular slots. Môn nhận xét requires 2 regular slots.
2. Assigned subject teacher creates a column with `kind=TX/GK/CK`, valid slot, and unique book/kind/slot.
3. Teacher batch enters score `[0,10]` with one decimal max, or qualitative PASS/FAIL/EXEMPT. Invalid item returns 400 without partial update.
4. Subject teacher from another class or another subject is denied; GVCN gets published only, cannot write course score by virtue of GVCN role alone.
5. Cannot lock until EVERY active enrollee has a grade/qualitative mark. Cannot directly edit a locked grade.
6. School Admin/Academic Affairs can publish only a LOCKED column; publish produces outbox event for currently verified guardians, without raw score.
7. Parent can see ONLY child's PUBLISHED entries with active, verified academic guardian link. Student sees ONLY self, through StudentAccount.
8. Other tenant must see 404 even if UUID is known.
9. Grade correction request on LOCKED/PUBLISHED requires reason, cannot submit same value or duplicate pending request.
10. Only admin/academic affairs may approve/reject; approval increments `GradeEntry.version` and records old/proposed/actor/time; repeated decisions denied.
11. Semester average generated only with complete configured number of TX and one GK and CK **published**. Weighted average uses Decimal and ROUND_HALF_UP.
12. COMMENT semester status only if all four expected published PASS/FAIL records; EXEMPT is displayed but not automatically classified.

## Kiểm chứng kỹ thuật — 2026-10-24

- Migration `grades.0001_initial` đã áp dụng trên PostgreSQL; drift check không có thay đổi.
- Bộ grade gồm 19 API tests, 15 pure-rule tests và 6 PostgreSQL concurrency tests. Chạy cùng 92 regression tests Sprint 0–2.
- 14 API client contract tests thực thi request/response (không chỉ tìm chuỗi trong source).
- Typecheck 6 app, build 3 React web và xuất iOS/Android bundle cho 3 Expo app đã qua.
- `pnpm expo:doctor`: cả 3 app tương thích; giữ nguyên dependency/lockfile Sprint 2.

Toàn bộ backend: PostgreSQL 132/132 đạt; SQLite 119 đạt và 13 ca PostgreSQL được bỏ qua. Reproduce: `bash scripts/verify_sprint3.sh` hoặc `docker compose exec -T backend python manage.py test apps.academics.tests apps.access.tests apps.attendance.tests apps.grades.tests`.

## Nghiệm thu thủ công còn lại

Chưa đánh dấu browser/thiết bị thật đã đạt. Công cụ điều khiển trình duyệt đã từng treo trong Sprint 2; lần này kiểm chứng tự động và đọc source không thay thế kiểm thử tương tác.

1. `admin_a` trên Admin Web → Sổ điểm → chọn lớp/môn, HK I, SCORE, hai cột TX. Chọn đúng môn được phân công cho `gvbm_a`.
2. `gvbm_a` trên Teacher Web → tạo TX1 → nhập điểm tất cả học sinh → lưu → khóa. Nếu thay giá trị rồi bấm khóa, hệ thống lưu giá trị mới trước khi khóa. Dữ liệu trống/sai phải báo lỗi và không khóa.
3. Parent/Student chưa thấy điểm ở DRAFT/LOCKED. Admin mở sổ, xác nhận công bố; tải lại kết quả trên Parent/Student Mobile để thấy điểm.
4. Thêm TX2/GK/CK và công bố đủ: trung bình mới xuất hiện. Ví dụ TX 7, 8; GK 8; CK 9 → 8,3.
5. GVCN (`gvcn_a`) chỉ xem cột đã công bố, không có quyền nhập môn khác. GV không được phân công phải bị từ chối từ API.
6. Teacher Web → Đề nghị sửa → nhập điểm khác và lý do tối thiểu 10 ký tự. Admin kiểm tra học sinh/môn/cột và giá trị cũ–mới, xác nhận duyệt. Parent/Student tải lại phải thấy điểm mới. Gửi/duyệt lặp phải bị chặn.
7. Teacher Mobile thử nhập và khóa. Parent có nhiều con thử đổi con; Student chỉ thấy chính mình. Thử đổi trường, logout, token hết hạn và mạng lỗi; không để dữ liệu phiên cũ xuất hiện lại.
8. Kiểm tra bàn phím, nhãn truy cập, cuộn bảng và màn hình nhỏ trên iOS/Android.

## Giới hạn còn giữ

- Chỉ demo với dữ liệu giả lập. Đây không phải học bạ chính thức hay chứng nhận tuân thủ quy định.
- DRAFT dùng roster hiện tại; LOCKED/PUBLISHED giữ membership bằng GradeEntry. Chưa snapshot tên/thông tin cá nhân tại ngày đánh giá, chưa có ngày đánh giá để xử lý đầy đủ chuyển lớp/học bù.
- EXEMPT chỉ Admin/giáo vụ nhập qua API; chưa có UI/hồ sơ miễn và không tự tổng hợp kết quả học kỳ khi có EXEMPT.
- Điều chỉnh trên Teacher Web + Admin Web; chưa có form điều chỉnh mobile.
- Thông báo công bố/điều chỉnh chỉ lưu outbox, không gửi push. Danh sách giới hạn pilot, chưa phân trang.
- Production auth, lịch học, policy theo số tiết, học bạ số/chữ ký số, bảo mật vận hành và xác nhận nghiệp vụ của trường vẫn là các bước riêng.
