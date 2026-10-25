# Sprint 5 — Nghiệm thu

Bản tích hợp phát triển trên Sprint 4 + Expo SDK 58. Dùng dữ liệu giả lập. Kết quả tự động và giới hạn xem [delivery manifest](SPRINT5_DELIVERY_MANIFEST.md).

| Hạng mục | Kiểm chứng kỹ thuật | Nghiệm thu trên thiết bị |
|---|---|---|
| Thông báo trường/khối/lớp | Draft ẩn với người nhận; publish đúng phạm vi; snapshot + quyền hiện tại; retry không tạo sự kiện trùng | Chờ người dùng |
| Liên hệ và hội thoại | Đúng lớp/giáo viên/người giám hộ; admin/support không đọc DM; khóa UUID chống gửi trùng | Chờ người dùng |
| Thu hồi quyền | Link, phân công, vai trò, chuyển lớp, năm học và inbox được kiểm tra lại | Chờ người dùng |
| Phiếu hỗ trợ | Parent chỉ phiếu của mình; staff cùng trường; claim khi phản hồi; phiên bản chống ghi đè | Chờ người dùng |
| Đã đọc/chưa đọc | Recipient-only; read watermark không nuốt tin đến sau khi tải | Chờ người dùng |
| Audit, transaction, migration | Audit các thay đổi; lỗi audit rollback; clean DB + upgrade/rollback/reapply riêng | Đã kiểm chứng bằng test |

## Điện thoại thật — cần chạy trước khi chốt sprint

1. Mở Teacher, Parent, Student trên Expo Go SDK 58 cùng Wi-Fi với Mac. Đăng nhập `gvcn_a`, `parent_a`, `student_a`.
2. Teacher chọn lớp, nhập tiêu đề/nội dung và **Lưu bản nháp**. Parent/Student làm mới: chưa thấy nháp. Teacher xem lại rồi **Công bố** và xác nhận. Hai app người nhận làm mới: thấy đúng nội dung và đánh dấu đọc được.
3. Parent chọn học sinh, chọn GVCN từ danh sách được xác minh và gửi tin. Teacher làm mới, mở hội thoại, phản hồi. Parent làm mới/mở lại: thấy phản hồi; số chưa đọc cập nhật. Tắt mạng khi gửi, bật lại rồi thử lại cùng nội dung: không bị nhân đôi.
4. Parent tạo yêu cầu hỗ trợ có loại và học sinh liên quan (hoặc yêu cầu chung). Mở Support Desk 5177, đăng nhập `support_a`, mở phiếu và phản hồi: tự nhận xử lý. Chuyển **Đã giải quyết**, rồi **Đã đóng**; Parent xem phản hồi, phiếu đóng không còn nút gửi phản hồi.
5. Student chỉ thấy thông báo và inbox, không có soạn tin hay tạo ticket. `gvbm_a` không có phần soạn thông báo lớp. `admin_a` không đăng nhập được Support Desk; Admin có hàng đợi riêng trong trang **Liên lạc & hỗ trợ**.
6. Đăng xuất/đổi trường khi đang tải, hết hạn JWT, đưa app nền rồi mở lại, bàn phím và màn hình nhỏ: không còn dữ liệu phiên cũ, lỗi hiển thị rõ. Kiểm tra tài khoản trường B không thấy nội dung A.

Ghi lại thiết bị/OS, tài khoản, bước, kết quả và ảnh lỗi nếu có. Chưa có APK/IPA ký, kiểm thử push/email hay nghiệm thu dữ liệu thật. Bộ export iOS/Android không thay thế kiểm thử thiết bị.
