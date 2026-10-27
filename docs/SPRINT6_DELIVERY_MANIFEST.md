# Sprint 6 — Delivery manifest

Ngày kiểm chứng local: 27/10/2026. Nền `sprint-5/communication-notifications`, triển khai trên `sprint-6/parent-student-dashboard`. Giữ Expo SDK 58, các màn hình Sprint 0–5 và dữ liệu demo hiện có.

## Thay đổi

- App Django `dashboard` chỉ đọc, 3 endpoint tổng hợp dữ liệu hiện hành; không thêm bảng hoặc migration.
- Parent/Student Mobile thêm dashboard, chọn con, empty/loading/error/refresh, giới hạn feed rõ ràng; Parent có tóm tắt theo quy tắc và nhãn nguồn.
- Shared typed client, native component/controller, kiểm thử API/rules/security/contracts, harness UI và tài liệu nghiệm thu.
- Sửa lỗi trong starter kit: tên field chuyên cần ở digest, quá hạn theo giờ, draft quá hạn, current year/enrollment, không tự chọn lớp khi nhiều enrollment khác nhau, event live authorization, tổng bài tập qua SQL, guards cho request chậm và JWT hết hạn.

## Bằng chứng

| Kiểm tra | Kết quả local |
|---|---|
| PostgreSQL full regression | **235 tests PASS**, gồm 28 ca Sprint 6 |
| API client contracts | **27 tests PASS**, 4 ca mới Sprint 6 |
| TypeScript | **7 app PASS** |
| Web production builds | **4 app PASS** |
| Mobile export | Teacher/Parent/Student có bundle iOS và Android; Parent/Student kiểm tra lại sau sửa preview race |
| Expo version checks | SDK 58 giữ nguyên; chạy `expo install --check` cho cả ba app |
| Schema | `makemigrations --check --dry-run`, `migrate --check`, Django system check; không thêm schema |
| Query scaling | Thêm 20 bài tập không tăng số query theo từng bài; tổng hợp SQL trước giới hạn feed |
| Live component QA | Parent/Student dashboard và preview dùng local API thật, render qua React Native Web/Chrome ở rộng 390px; không tràn ngang |
| UI race/error QA | Snapshot/preview cũ không ghi đè con mới; preview 500 giữ snapshot; 404 xóa dữ liệu; 401 hết phiên; hồ sơ rỗng; không lỗi React runtime |
| Visual QA | Đã xem ảnh Parent và Student, kiểm tra nhãn, dữ liệu thiếu, thứ tự nhiệm vụ, nguồn tóm tắt |

Harness UI chỉ kiểm tra component và request lifecycle; **chưa thay thế Expo Go, SecureStore, iOS/Android thật, background/resume hoặc accessibility audit**. Không có signed APK/IPA, EAS/store release, load test hoặc security pentest. CI trên GitHub được ghi ở PR Sprint 6 sau khi chạy trên commit cuối.

Report PDF và sơ đồ kit được giữ nguyên làm tài liệu tham khảo; các kết quả “not run” trong report là tình trạng của tác giả kit, không phải kết quả của bản tích hợp này. Chạy lại theo [implementation](SPRINT6_IMPLEMENTATION.md), nghiệm thu thiết bị theo [acceptance](SPRINT6_ACCEPTANCE.md).

## Giới hạn có chủ đích

Dữ liệu học tập theo lớp hiện tại; danh sách có giới hạn; refresh thủ công. Throttle dùng cache hiện tại, chưa phục vụ hệ thống nhiều worker lớn. Không có LLM, chẩn đoán, dự đoán học sinh, tự sửa điểm, timetable, push/email/SMS hay triển khai dữ liệu thật. Tóm tắt chỉ có số liệu và source labels; không xuất tin nhắn, bài làm, lý do xin nghỉ hay ghi chú của giáo viên.
