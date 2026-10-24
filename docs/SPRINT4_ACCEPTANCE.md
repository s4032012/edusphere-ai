# Sprint 4 — Acceptance & threat-driven test plan

| Test | Scenario | Expected |
|---|---|---|
| H01 | Teacher has active subject/class assignment | Can create draft homework. |
| H02 | Unassigned subject teacher | Cannot create or review work (403/404). |
| H03 | Student or parent attempts create/close | Refused. |
| H04 | Task DRAFT | Hidden from student/parent, shown to original teacher. |
| H05 | Publish draft | Task listed for enrolled student and verified guardian. |
| H06 | Student submits answer before due | SUBMITTED record created, audit event. |
| H07 | Student saves draft | DRAFT visible only to student and authorized teacher. |
| H08 | Student supplies stale version | 409; no overwrite. |
| H09 | Student attempts submission after due | Refused when allow_late=false. |
| H10 | Student attempts after closed | Refused even if allow_late=true. |
| H11 | Teacher returns feedback with valid score | RETURNED, audit, notification intent. |
| H12 | Student resubmits after RETURNED | Refused. |
| H13 | Parent linked to child but unverified | No academic data. |
| H14 | Parent tries child not linked | 404. |
| H15 | Cross-tenant task/submission guessed by UUID | 404. |
| H16 | GVCN opens class roster | Read-only; no grading. |
| H17 | Homework score shown in app | Must be labeled non-official; does not modify GradeEntry. |
| H18 | Browser/mobile navigation tests | Fetch only authorized tasks; no data shared across login switches. |
| H19 | PostgreSQL integration & migrations | Must complete before pilot. |
| H20 | Expo builds & E2E | Must complete before pilot. |

## Kết quả kỹ thuật — 2026-10-24

- Migration `homework.0001_initial` áp dụng thành công trên PostgreSQL; không có schema drift.
- PostgreSQL: **173/173 PASS**, gồm 41 ca Homework (23 API/security, 12 rules, 6 concurrency) và 132 ca hồi quy Sprint 0–3.
- Concurrent first save/update/return dùng cùng tenant lock và kiểm tra version; một request thắng, request cũ nhận 409. Submit so với close/return giữ đúng trạng thái cuối, không chấm bài đã bị sửa sau khi đọc.
- 18 API client contract tests, typecheck 6 app, build 3 web, Expo dependency check 3 app và iOS/Android bundle export cho 3 app: PASS.
- Chrome headless: đã chạy tạo/sửa/giao bài, trả nhận xét, đóng bài, đổi tài khoản GVCN chỉ đọc; student submit và parent redaction được kiểm tra qua HTTP API trong cùng luồng. Không có JS page error. Kiểm tra ảnh Teacher/GVCN không thấy lỗi bố cục.
- Bundle export không phải bản cài native đã ký, không thay thế kiểm thử trên điện thoại thật.

## Nghiệm thu thủ công — chờ người dùng

1. Teacher Web `gvbm_a`: chọn lớp/môn được phân công → tiêu đề, hướng dẫn, hạn tương lai → Lưu nháp. Sửa nháp, kiểm tra thời gian và bật/tắt nộp muộn, rồi xác nhận Giao bài. HS/PH không thấy nháp.
2. Teacher Mobile: thử cùng luồng bằng bộ chọn ngày/giờ; kiểm tra giờ hiển thị đúng múi giờ thiết bị và deadline qua API.
3. Student Mobile `student_a`: chọn bài → lưu nháp trống, nhập bài rồi nộp. Sửa nội dung và Nộp lại; không chuyển bài đã nộp về nháp. Sau hạn phải bị từ chối trừ khi cho nộp muộn; sau Đóng luôn bị chặn.
4. Giáo viên mở roster, đọc nội dung, nhập nhận xét/điểm (0–10, tối đa một số thập phân), xác nhận Trả bài. Student thấy kết quả và không sửa tiếp được. Điểm sổ chính thức Sprint 3 không thay đổi.
5. Parent `parent_a`: tải lại để xem trạng thái/nhận xét/điểm bài tập, không thấy nội dung bài làm, không có thao tác nộp hộ. Nếu có nhiều con, đổi con và kiểm tra nội dung cũ được xóa khi tải.
6. GVCN `gvcn_a`: xem tiến độ và phản hồi lớp chủ nhiệm, không thấy nội dung bài làm hay nút tạo/giao/đóng/trả bài. Admin có quyền API chỉ đọc; không có màn Homework mới ở Admin Web.
7. Mở hai phiên học sinh cùng một bài: phiên thứ nhất cập nhật, phiên thứ hai nộp bản cũ nhận 409, giữ văn bản để sao chép và có nút tải phiên bản mới. Giáo viên đang xem bản cũ cũng phải tải lại trước khi chấm.
8. Đổi trường/đăng xuất/đổi tài khoản, mạng lỗi và token hết hạn: không xuất hiện dữ liệu phiên cũ, có thông báo lỗi và tải lại được. Thử bàn phím/cuộn/chữ lớn/ngày giờ trên iOS và Android.

Chỉ đánh dấu sprint nghiệm thu sau khi người dùng xác nhận luồng thực tế. Chưa dùng dữ liệu thật; upload, AI, push/email thật, lịch sử phân lớp và rà soát trước pilot nằm ngoài bản giao này.
