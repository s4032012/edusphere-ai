# Sprint 6 — Parent & Student Dashboard

Bản tích hợp ngày 27/10/2026 dựa trên nhánh Sprint 5 đang chạy, giữ Expo SDK 58 và các chức năng cũ. Report/diagram gốc trong `docs/` là tài liệu thiết kế của kit; trạng thái kiểm chứng bản tích hợp ở [delivery manifest](SPRINT6_DELIVERY_MANIFEST.md).

## Phạm vi

Parent Mobile có tổng quan theo từng con; Student Mobile ưu tiên bài chưa nộp còn nhận bài. Dashboard nằm ngay dưới phần tài khoản, trước các màn hình chi tiết đã có. Chọn hồ sơ trong danh sách API cấp quyền, làm mới tổng quan và xem thời điểm cập nhật. Không có quyền quản trị tự mở rộng danh sách học sinh trong hai app consumer.

Dữ liệu gồm lớp hiện tại, chuyên cần 30 ngày, tối đa 8 kết quả đã công bố, 8 bài tập ưu tiên, 5 tiêu đề thông báo đúng phạm vi học sinh và 5 sự kiện tài khoản. Parent xem thêm bản tóm tắt theo quy tắc có nhãn nguồn. Không gọi LLM, không dự đoán/chẩn đoán, không truyền dữ liệu sang nhà cung cấp AI.

## API chỉ đọc

Mọi endpoint yêu cầu Bearer JWT và `X-Tenant-ID`. Chỉ vai trò PARENT/STUDENT cùng quan hệ hiện hành; SCHOOL_ADMIN riêng trả 403, học sinh ngoài quyền trả 404.

| GET | Kết quả |
|---|---|
| `/api/v1/dashboard/children/` | Tối đa 30 hồ sơ được liên kết/xác minh, theo mã học sinh |
| `/api/v1/dashboard/students/{id}/` | Snapshot dữ liệu tổng hợp của một học sinh |
| `/api/v1/dashboard/students/{id}/ai-preview/` | Tóm tắt deterministic, source labels, các cờ model/export false |

`Cache-Control: private, no-store` và Vary theo Authorization/X-Tenant-ID áp dụng cả lỗi. Throttle riêng 60 request/phút/tài khoản/trường bằng cache Django; cần shared cache nếu chạy nhiều worker. Không có POST/PATCH/DELETE trên dashboard.

## Quy tắc dữ liệu

- GuardianLink phải đúng tenant, được xác minh, active, còn hiệu lực và `can_view_academic=True`; StudentAccount chỉ ánh xạ hồ sơ trong tenant. Học sinh lưu trữ không xuất hiện. Membership và quan hệ được đọc lại mỗi request.
- Ghi danh phải active, còn hiệu lực trong năm học hiện tại, và cả lớp/năm/học sinh cùng tenant. Không có ghi danh: `enrollment_status=NONE`; nhiều lớp khác nhau đang active: `AMBIGUOUS`. Hai trường hợp trả thông tin hồ sơ, trạng thái rõ ràng và feed học tập rỗng; không tự chọn lớp mới nhất. Hai enrollment trùng cùng lớp không nhân đôi dữ liệu.
- Chuyên cần chỉ lấy ngày hôm nay và 29 ngày trước, session SUBMITTED/LOCKED, đúng lớp hiện tại. Ngày không có bản ghi không tính là có mặt hoặc vắng. Thiếu dữ liệu hiển thị dấu “—” cùng giải thích.
- Điểm chỉ lấy Assessment PUBLISHED, kiểm tra tenant cả entry/assessment/book/subject; hiển thị điểm số (kể cả 0), kết quả nhận xét và ghi chú đã công bố. Không tính trung bình. Tóm tắt chỉ đếm tối đa 8 kết quả trong feed, nói rõ đây không phải toàn bộ học bạ.
- Bài tập PUBLISHED/CLOSED của lớp hiện tại, chỉ trạng thái submission của học sinh đang xem. Hạn nộp dùng **thời điểm có múi giờ**, kể cả quá hạn trong cùng ngày; draft chưa nộp quá giờ cũng là OVERDUE. RETURNED/SUBMITTED giữ trạng thái. Bài đóng hoặc không cho nộp muộn không được gợi ý là nhiệm vụ còn làm được.
- Tổng bài tập được aggregate trong SQL trước khi giới hạn 8 mục. Ưu tiên bài quá hạn còn nhận bài, rồi bài chưa nộp còn hạn; sau đó mới đến các mục chỉ đọc. Không tải toàn bộ nội dung bài nộp vào Python. Tổng quá hạn có thể gồm bài đã đóng và được ghi rõ.
- Thông báo cần snapshot người nhận, quyền hiện tại theo policy Sprint 5 và scope trùng lớp/khối/trường của học sinh đang xem. Không trả nội dung thông báo, chỉ metadata/tiêu đề. Tối đa 5 mục trong 100 ứng viên gần đây.
- Sự kiện inbox giữ policy truy cập hiện tại của Sprint 5, kể cả sự kiện cũ; không chỉ dựa vào recipient. Chỉ trả id, loại, thời gian, read. Tối đa 5 mục trong 300 ứng viên gần đây, scope ACCOUNT có thể liên quan nhiều học sinh. Không trả payload hoặc nội dung tin nhắn.
- Snapshot/tóm tắt không sửa trạng thái đọc, điểm, bài tập hoặc audit. Không có bảng, migration hay kho dữ liệu học sinh mới.

## Giao diện và vòng đời request

`packages/communications-ui/dashboard.tsx` là component native dùng chung với mode Parent/Student; hai app có wrapper riêng. Controller có request sequence theo học sinh và mount theo token/trường. Kết quả chậm không được ghi đè học sinh mới. Tóm tắt của con cũ không hiển thị sau đổi con và không chặn tóm tắt của con mới.

401 gọi luồng đăng xuất hiện có. 403/404 xóa snapshot/tóm tắt và danh sách nhạy cảm. Lỗi mạng/500 của tóm tắt hiển thị riêng, giữ snapshot đã tải. Refresh lỗi mạng giữ dữ liệu cũ với thời điểm và cảnh báo. Có loading, retry, empty state, trạng thái chữ, touch target tối thiểu 48; kiểm tra screen reader/native OS còn chờ.

## Chạy

```bash
pnpm install --frozen-lockfile
docker compose exec backend python manage.py check
docker compose exec backend python manage.py migrate --check
pnpm dev:parent --clear
# terminal khác
pnpm dev:student --clear
```

Giữ nguyên `.env` API LAN hiện có và Expo Go SDK 58. Không cần reset DB hoặc seed lại. Backend development tự reload source đang mount. Không khởi động Compose chỉ localhost để thay thế cấu hình LAN đang dùng.

Parent demo: `parent_a`, Student demo: `student_a`; mật khẩu `DemoOnly!ChangeMe123`. Dashboard tự tải, không cần bấm xem danh sách học sinh trước. Các tính năng bài tập/liên lạc vẫn ở bên dưới.

## Kiểm tra lại

```bash
bash scripts/verify_sprint6.sh
# PostgreSQL thay vì SQLite mặc định của script local:
docker compose exec backend python manage.py test apps.academics.tests apps.access.tests apps.attendance.tests apps.grades.tests apps.homework.tests apps.communications.tests apps.dashboard.tests
pnpm expo:doctor
pnpm build:mobile
```

Harness QA render component native qua React Native Web, dùng backend demo local; không thay đổi dependency production:

```bash
npm install --prefix /tmp/edusphere-s6-ui --no-audit --no-fund react-native-web@~0.21.4 react@19.3.0 react-dom@19.3.0 playwright
DASHBOARD_QA_DEPS=/tmp/edusphere-s6-ui node scripts/dashboard-ui-qa/server.mjs
# terminal khác; cần Chrome local
PLAYWRIGHT_MODULE=/tmp/edusphere-s6-ui/node_modules/playwright/index.mjs node scripts/dashboard-ui-qa/browser.mjs
```

Harness chạy trên 127.0.0.1:5186, proxy API localhost; chỉ GET dữ liệu dashboard demo, sau đó mock response để thử race/expiry/revocation. Ảnh ở `/tmp/edusphere-s6-*.png`. Đây không phải kiểm thử Expo Go, SecureStore, iOS/Android hay signed APK/IPA.

## Giới hạn

Không có pagination lịch sử, cache read model, lịch học, deep-link sang từng bài, push/email/SMS, AI thực, consent/provider integration hay triển khai production. Phạm vi học tập là lớp đang học, không tổng hợp lịch sử chuyển lớp. Cần nghiệm thu thiết bị, accessibility, tải lớn và quy trình quyền dữ liệu trước khi dùng dữ liệu thật.
