# Gate từ Sprint 0 sang Sprint 1

Trạng thái chi tiết và bằng chứng chạy lệnh: [VERIFY.md](VERIFY.md). Phạm vi và mapping report: [SPRINT0_SCOPE.md](SPRINT0_SCOPE.md).

| Gate | Trạng thái | Điều kiện còn lại |
| --- | --- | --- |
| G-01 Compose/Postgres/seed/health | PASS local | Không thay thế triển khai production |
| G-02 Install/typecheck/web build/Expo check | PASS local | Lockfile hiện có; native bundles cũng pass |
| G-03 Role đúng/sai trên ba điện thoại | PARTIAL | API/role-filter tests pass; người dùng báo mobile hoạt động sau sửa LAN, còn xác nhận ca đúng/sai role từng app |
| G-04 Cross-tenant isolation | PASS cho API Sprint 0 | Duy trì regression cho API mới |
| G-05 Assignment/guardian scope | PASS cho API Sprint 0 | UI/native smoke cần xác nhận |
| G-06 Expiry/logout/SecureStore | IMPLEMENTED | Timer/401/in-flight guard có trong mã; cần kiểm tra SecureStore và background/resume trên thiết bị |
| G-07 Migrations/schema/Postgres CI | PARTIAL | Migrations có và test Postgres pass; cần commit, Phase1 SQL nguồn và CI remote |
| G-08 Auth production decision | PENDING owner | Đề xuất trong SPRINT0_SCOPE.md cần chủ dự án phê duyệt |
| G-09 UI/a11y review | PARTIAL | Người dùng xác nhận admin, GVCN, GVBM đăng nhập/xem roster trên web; mobile đã được người dùng báo hoạt động; còn visual/keyboard/screen-reader QA |
| G-10 CI/branch protection | PARTIAL | Workflow frozen lockfile + Postgres có sẵn; cần remote repo và bật required checks |

## Kịch bản QA thiết bị khi có runtime

1. Mở Teacher, Parent, Student với các Metro port 8081/8082/8083; cấu hình API URL đúng thiết bị theo README.
2. Đăng nhập đúng role, tải roster A; dùng account sai role phải ở lại màn login và không lưu token.
3. Parent chỉ thấy con được xác minh; Student chỉ thấy bản thân; GVBM chỉ thấy học sinh lớp được phân công.
4. Đăng xuất rồi khởi động lại app: không tự vào phiên cũ. Chờ JWT hết hạn và thử resume sau khi để app nền: yêu cầu đăng nhập lại, không còn roster cũ.
5. Đổi trường/logout khi request đang chậm: response cũ không được hiển thị lại. Network lỗi có thông báo và cho retry.
6. Kiểm tra bàn phím, screen reader, cỡ chữ, safe area và màn hình nhỏ trên cả iOS/Android; ghi thiết bị/OS và kết quả.

Không cần chờ các module Phase 1 (điểm, chuyên cần, messaging, AI) để kiểm thử nền Sprint 0; không đánh dấu các module đó đã làm chỉ vì có nhãn navigation.
