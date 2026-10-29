# Sprint 7 — Ổn định và tích hợp hệ thống

Sprint 7 bổ sung kiểm chứng cho code Sprint 0–6, không thêm nghiệp vụ hoặc AI. Nền tích hợp là commit Sprint 6 `b932f8d`, giữ Expo SDK 58, các migrations đã commit và `pnpm-lock.yaml`. Báo cáo/kit gốc nói thiếu migrations và lockfile vì dùng snapshot cũ; các lỗi đó không còn trên repo này. Không chép đè code bằng starter kit.

## Thay đổi

- `/healthz/`: liveness, không truy vấn database. `/readyz/`: chạy `SELECT 1`, trả 200 khi kết nối được, 503 với JSON chung khi lỗi. Cả hai hỗ trợ GET/HEAD, từ chối ghi và không cache. PostgreSQL có connect timeout 5 giây. Readiness không khẳng định migration, phân quyền hay pilot đã đạt.
- `apps.regression.tests`: 12 tình huống tenant/vai trò từ kit; 7 kiểm thử health/seed; 10 luồng API tích hợp và 1 lớp 45 học sinh. JWT thật đi qua DRF, dữ liệu và transaction thật trong PostgreSQL test database. Đây là API integration, không phải device E2E.
- Các luồng kiểm tra việc công bố dữ liệu qua dashboard, điểm 0, giữ nháp kín, nộp bài lặp, tin nhắn lặp, support không đọc hội thoại riêng, thu hồi guardian/teacher ngay khi JWT còn hạn.
- Giữ guard `seed_demo` khi DEBUG=False và startup không tự tạo migrations; thêm kiểm thử runtime. Seed lặp không reset mật khẩu đã đổi hoặc bật lại guardian đã bị thu hồi.
- CI chạy toàn bộ 8 nhóm backend tests, source safeguards, tests cho release gate, smoke HTTP bằng 7 tài khoản và kịch bản DB mất kết nối. Giữ 27 API client tests, 7 app typechecks, 4 web builds, 3 app Expo compatibility checks và iOS/Android exports.
- Sửa lỗi raw JSX whitespace ở Teacher Attendance gây lỗi runtime khi login; thêm native JSX guard và 2 regression tests. Smoke iOS Teacher/Parent được ghi ở [biên bản simulator](SPRINT7_IOS_SMOKE.md).
- Gate thủ công kiểm tra đúng commit, working tree sạch, P0/P1 bằng 0, PASS/người duyệt/ngày duyệt và file evidence đúng SHA-256. Không tự tạo signoff. Công cụ chỉ kiểm tra hồ sơ, không xác thực chữ ký hay cấp chứng nhận pháp lý.

Không có schema mới. Không cần generate migrations, reset hoặc seed lại DB đang dùng. Cập nhật các bản vá Expo SDK 58 theo compatibility check (Expo, Constants, Linking, Router, React Native và Metro) đồng bộ cả 3 app và lockfile; giữ port Metro và `.env` LAN.

Node cần >=22.13.0. Repo có `.nvmrc` và engine gate để chặn Node 20 trước khi chạy Expo (Node cũ làm Metro lỗi `URL.parse is not a function`). Nếu dùng nvm: chạy `nvm use` tại thư mục gốc. Luôn chạy các lệnh `pnpm dev:*` từ root.

## Chạy lại kiểm tra

Từ thư mục gốc, với Docker stack development đang chạy:

```bash
# Source/rules/contracts và tests cho các gate; không khẳng định runtime pass
bash scripts/verify_sprint7.sh

# PostgreSQL + build + HTTP + probe outage + recovery trên DB tạm
bash scripts/verify_sprint7.sh --full
```

`--full` dùng `docker compose exec`, không recreate stack nên giữ binding LAN đang dùng. Database hiện tại chỉ được check migration và đọc API; integration tests ghi vào `test_edusphere`. Không chạy đồng thời hai bộ Django test cùng dùng tên database test này. Dependencies dùng frozen lockfile. Lệnh `expo:doctor` của repo thực tế là `expo install --check`, không phải toàn bộ công cụ `expo-doctor`. `build:mobile` xuất JS/Hermes cho iOS/Android, không tạo APK/IPA và không thay thế chạy Expo Go trên thiết bị.

Nếu thiếu prerequisites, command dừng với lỗi; không chuyển skip thành PASS. HTTP smoke chỉ chấp nhận loopback có port, không đi theo redirect, không in token/password/response riêng tư. Nó cần sẵn tài khoản demo còn hiệu lực và không tự reset dữ liệu để làm test xanh.

## Kiểm tra vận hành

`python3 scripts/sprint7_recovery_drill.py` tạo hai database tên ngẫu nhiên `s7_drill_*`. Database thứ nhất được migrate + seed synthetic; script kiểm tra reapply migrations, dump bằng PostgreSQL 17 `pg_dump`, restore sang database thứ hai, đối chiếu SHA-256 từng bảng và kiểm tra quyền parent/cross-tenant sau restore. Cả hai database và dump tạm đều được dọn. Không lấy backup từ DB ứng dụng. Thời gian này chỉ là số đo trên dataset nhỏ, không phải RTO của trường.

`docker compose exec -T backend python < scripts/sprint7_probe_drill.py` đổi kết nối của tiến trình kiểm tra sang port không có DB, xác nhận ready 200 → 503 → 200 và live vẫn 200. Không stop PostgreSQL hoặc sửa cấu hình server đang phục vụ.

Xem [runbook vận hành](SPRINT7_OPERATIONS.md), [ma trận](SPRINT7_TEST_MATRIX.md), [kết quả](SPRINT7_DELIVERY_MANIFEST.md) và [nghiệm thu](SPRINT7_ACCEPTANCE.md).

## Giới hạn còn phải khép lại

Nghiệm thu Teacher/Parent/Student trên iOS và Android, VoiceOver/TalkBack/chữ lớn/mạng yếu, chứng cứ luồng UI, security/privacy review, monitoring/alert thật và school UAT chưa được thay bằng kiểm thử API. Account invitation, refresh/revoke từng thiết bị và lost-device recovery chưa có luồng hoàn chỉnh; membership/guardian/assignment revoke có kiểm thử runtime. Không có push worker/email/SMS hoặc AI provider. Chưa chốt GO pilot dữ liệu thật.
