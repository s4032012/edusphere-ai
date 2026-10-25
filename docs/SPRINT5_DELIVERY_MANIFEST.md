# Sprint 5 — Delivery manifest

Ngày kiểm chứng: 26/10/2026. Nền: nhánh `sprint-4/assignment-homework` (bao gồm Expo SDK 58). Nhánh triển khai: `sprint-5/communication-notifications`. Đây là bản tích hợp prototype với dữ liệu giả lập; chờ nghiệm thu trên điện thoại thật.

## Đã triển khai

- `backend/apps/communications`: 9 bảng mới, migration `0001_initial`, quyền truy cập theo quan hệ hiện tại, thông báo có danh sách người nhận tại thời điểm công bố, hội thoại văn bản, phiếu hỗ trợ, read receipts và audit.
- Giao diện dùng chung `packages/communications-ui`: Admin/Teacher Web, Teacher/Parent/Student Mobile; Support Desk mới ở cổng 5177. Lưu nháp/công bố tách biệt, chọn lớp/liên hệ qua danh sách, phiên đăng nhập được cô lập theo trường.
- Hợp đồng API thực thi, kiểm thử PostgreSQL đồng thời và các ca từ chối quyền. CI mở rộng gồm communications và Support Web.
- Demo `support_a`/`support_b`; không reset tài khoản/dữ liệu các sprint trước. CORS 5177 và hướng dẫn giữ API LAN.

## Bằng chứng kiểm chứng local

| Kiểm tra | Kết quả |
|---|---|
| Backend toàn bộ Sprint 0–5 | 203 ca PASS trên PostgreSQL 17 trước khi thêm 4 ca cuối |
| Bộ Sprint 5 cuối cùng | 34 ca PASS, gồm 5 ca concurrency; tổng hiện tại dự kiến 207 ca khi chạy đầy đủ |
| API client | 23 ca thực thi PASS (5 ca mới Sprint 5) |
| TypeScript | 7 app PASS |
| Web production build | 4 app PASS |
| Mobile export | 3 app × iOS/Android PASS; JS/Hermes bundles, không phải APK/IPA ký |
| Expo version check | Cả 3 app `expo install --check` PASS, SDK 58 giữ nguyên |
| Migration | Clean schema qua bộ test; isolated Sprint 4 + seed → Sprint 5 → rollback → reapply PASS, học sinh trước nâng cấp không đổi |
| Demo runtime | Migration áp dụng; seed bổ sung support; backend giữ localhost + LAN; không có migration chưa tạo |
| Chrome E2E | GVCN draft/publish; parent API → teacher UI nhắn tin hai chiều; parent API → Support UI claim/resolve/close; Admin queue; từ chối admin vào Support Desk; logout; không lỗi React runtime |
| Visual QA | Đã xem ảnh Admin, Teacher và Support Desk; sửa khoảng đệm form Admin và selector Support |

Dữ liệu test Chrome chỉ là các bản ghi giả lập có tiền tố `Sprint 5 QA`. Parent/Student mobile chưa được thao tác trên thiết bị trong phiên này. Chưa chứng nhận accessibility, kiểm thử tải, penetration test hay tính sẵn sàng production.

## Chạy lại

```bash
bash scripts/verify_sprint5.sh
# PostgreSQL, thay vì SQLite mặc định của script local:
docker compose exec backend python manage.py test apps.academics.tests apps.access.tests apps.attendance.tests apps.grades.tests apps.homework.tests apps.communications.tests
docker compose exec -T backend python < scripts/verify_sprint5_migrations.py
pnpm expo:doctor
pnpm build:mobile
# Optional browser runner with Playwright installed externally:
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node scripts/browser_sprint5.mjs
```

## Giới hạn

Chỉ văn bản, manual refresh, danh sách có giới hạn. Không có gửi push/email/SMS, realtime, tệp đính kèm, lịch gửi, refresh token, moderation, retention enforcement hay production deployment. `QUEUED` chỉ là trạng thái outbox. Khóa ghi theo trường và fanout đồng bộ tối đa 2.500 người nhận phù hợp demo nhỏ; chưa qua load test. Throttle dùng cache theo tiến trình, cần shared cache khi triển khai nhiều worker.

Report gốc và sơ đồ kit giữ trong `docs/` để tham khảo thiết kế, bao gồm trạng thái kiểm chứng cũ của tác giả kit; manifest này ghi kết quả của bản tích hợp thực tế. Xem [nghiệm thu thiết bị](SPRINT5_ACCEPTANCE.md) trước khi chốt Sprint 5.
