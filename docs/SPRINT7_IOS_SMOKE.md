# Sprint 7 — iOS Simulator smoke

Ngày 29/10/2026, iPhone 17 Pro simulator, iOS 26.5, Expo Go SDK 58, Expo 58.0.21 / React Native 0.88.0 tại thời điểm smoke, API local `127.0.0.1:8000`. Metro kiểm thử chạy trên port riêng 18081–18083; không đổi `.env` hoặc port mặc định của người dùng. Các bước dưới được quan sát qua giao diện Simulator và accessibility tree, dùng dữ liệu demo có sẵn, không gửi thông báo hoặc tạo bản ghi nghiệp vụ.

| App | Quan sát | Kết quả |
|---|---|---|
| Teacher | Khởi chạy, đăng nhập `gvcn_a`, chọn đúng tenant/role, tải `Học sinh thử nghiệm A` / `HS001`, hiển thị lớp `8A1`, logout trở về login và xóa roster | PASS smoke |
| Parent | Khởi chạy, đăng nhập `parent_a`, tự tải dashboard đúng con/lớp, hiển thị homework đã trả và thông báo; mở tóm tắt theo quy tắc có nguồn, không gửi provider; logout xóa dashboard | PASS smoke |
| Student | Chưa thao tác login trên simulator; công cụ capture Simulator bị lỗi kết nối trước bước kiểm tra Student | NOT VERIFIED |
| Android cả 3 app | Máy chưa có Android SDK/emulator | NOT RUN |

Sau smoke, compatibility metadata của Expo yêu cầu React Native 0.88.1 và bộ dependency được cập nhật tương ứng. Kết quả Teacher/Parent dưới đây là bằng chứng của lần thử trước bản vá RN; cần kiểm tra lại cả 3 app trên dependency cuối trước signoff.

## Lỗi tìm thấy và xử lý

- Shell mở trực tiếp trong thư mục app dùng Node 20, khiến Expo Metro lỗi `URL.parse is not a function`. Chạy từ workspace với Node 22.19.0 đã khởi chạy được. Thêm `.nvmrc`, Node engines >=22.13 và `engine-strict` để phát hiện sớm.
- Teacher sau login báo `Text strings must be rendered within a Text component` tại màn hình điểm danh. Nguyên nhân là khoảng trắng JSX đơn trên cùng dòng giữa hai expression trong `View`. Đã bỏ khoảng trắng, xác minh giao diện tiếp tục tải roster/lớp và logout. Thêm native JSX guard + 2 regression tests vào CI.
- Còn warning deprecation `SafeAreaView` từ React Native; không chặn các thao tác đã quan sát. Đây không phải crash và không được tính thành chứng cứ accessibility pass.

Đã từ chối lưu mật khẩu demo vào Passwords. Sau kiểm tra, đã dừng đúng ba Metro tạm do phiên này tạo. Không coi smoke này là đủ J01–J10, mạng yếu, accessibility, physical-device testing hoặc chữ ký nghiệm thu iOS. Gate `native_ios` vẫn chưa hoàn tất vì thiếu Student và các thao tác nghiệm thu đầy đủ.
