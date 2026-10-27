# Sprint 6 — Nghiệm thu

Bản tích hợp sử dụng dữ liệu giả lập. Xem [kết quả kỹ thuật](SPRINT6_DELIVERY_MANIFEST.md) và [quy tắc/API](SPRINT6_IMPLEMENTATION.md). Chưa có AI bên ngoài.

| Hạng mục | Đã kiểm chứng tự động | Còn nghiệm thu |
|---|---|---|
| Phạm vi phụ huynh/học sinh | Verified link/self, membership, mixed admin roles, khác tenant, thu hồi và lưu trữ | Tài khoản demo trên điện thoại |
| Lớp và năm học | Hết năm/ghi danh, nhiều lớp, chuyển lớp, không tự suy ra lớp | Thông báo trạng thái rõ trên thiết bị |
| Chuyên cần/điểm | 30 ngày inclusive, bỏ draft, chỉ điểm công bố, điểm 0/nhận xét | Đối chiếu dữ liệu tạo từ màn hình nghiệp vụ |
| Bài tập | Quá hạn theo giờ, draft quá hạn, bài đóng, nộp muộn, tổng không bị cắt theo feed | Giao/nộp/trả bài rồi làm mới dashboard |
| Thông báo/inbox | Snapshot + quyền hiện tại + đúng con, inbox account-wide có nhãn, không lộ payload | Mở đọc ở Liên lạc rồi làm mới tổng quan |
| Tóm tắt | Không gọi model/export, nhãn nguồn, số liệu có giới hạn, không trích bài làm/tin nhắn | Nội dung dễ hiểu với phụ huynh |
| Request/UI | Chuyển con nhanh, snapshot/preview về chậm, 500 giữ snapshot, 404 xóa dữ liệu, 401 hết phiên, empty state | Expo Go, nền/resume, screen reader |

## Thử trên điện thoại thật

1. Mở Parent và Student với Expo Go SDK 58, giữ cấu hình API LAN đang hoạt động. Đăng nhập `parent_a` / `student_a`, mật khẩu demo trong README. **Tổng quan học tập của con / Tiến độ của em** phải tự tải dưới phần tài khoản.
2. Parent chọn con; kiểm tra tên/lớp và thời điểm cập nhật. Nếu có hai hồ sơ, đổi nhanh giữa hai con: nội dung phải theo đúng con đang chọn.
3. Student thấy nhiệm vụ còn làm được ở đầu. Bài đã đóng/hết hạn không cho nộp muộn không được gợi ý tiếp tục làm; bài đã nộp/đã trả vẫn xem được. Tạo hoặc nộp bài ở màn hình nghiệp vụ, rồi **Làm mới tổng quan** để đối chiếu.
4. Điểm nháp/khóa chưa công bố không xuất hiện. Sau khi Admin công bố, làm mới: thấy điểm/nhận xét. Không có số trung bình tự tạo. Điểm 0 phải hiển thị là 0, không bị coi là thiếu dữ liệu.
5. Chuyên cần chỉ ngày đã nộp/khóa trong 30 ngày. Khi chưa có bản ghi phải nói rõ thiếu dữ liệu, không kết luận đi học đầy đủ. Bài quá hạn trong cùng ngày phải được nhận đúng theo giờ.
6. Parent bấm **Xem tóm tắt theo quy tắc**: có nguồn cho từng câu và nhãn chưa sử dụng AI. Đổi con khi đang tải: không hiện tóm tắt của con cũ. Không có nội dung tin nhắn/bài làm nguyên văn trong tóm tắt.
7. Thông báo theo lớp/khối chỉ xuất hiện ở con đúng phạm vi. Mục cập nhật tài khoản có thể liên quan nhiều con và ghi rõ điều đó. Đọc thông báo ở phần Liên lạc, làm mới dashboard để cập nhật trạng thái.
8. Mất mạng/lỗi tải: có lỗi và nút thử lại, không tráo dữ liệu con khác. Đăng xuất/đổi trường/hết JWT: không còn dữ liệu phiên trước. Nhờ Admin thu hồi liên kết trên bộ dữ liệu thử: request kế tiếp bị từ chối và xóa nội dung nhạy cảm.
9. Thử màn hình nhỏ, phóng to chữ, VoiceOver/TalkBack, nền/resume trên iOS/Android. Ghi thiết bị, OS, bước và kết quả.

Chỉ chốt nghiệm thu chức năng sau khi các bước thiết bị đạt. Export JS/Hermes bundles không phải APK/IPA ký hoặc chứng nhận readiness cho dữ liệu thật.
