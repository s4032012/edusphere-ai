# EduSphere AI · Sprint 6 — Parent & Student Dashboard

**Sprint 6 đã tích hợp:** Parent/Student Mobile có dashboard tự tải theo học sinh, chuyên cần 30 ngày, điểm đã công bố, bài tập ưu tiên và thông báo. Parent xem tóm tắt **theo quy tắc, chưa sử dụng AI**, có nguồn cho từng câu. Xem [hướng dẫn/API](docs/SPRINT6_IMPLEMENTATION.md), [kết quả kiểm chứng](docs/SPRINT6_DELIVERY_MANIFEST.md) và [nghiệm thu thiết bị](docs/SPRINT6_ACCEPTANCE.md).

Chạy lại Metro: `pnpm dev:parent --clear` và `pnpm dev:student --clear` ở hai terminal. Giữ Expo Go SDK 58 và `.env` API LAN. Không cần reset/seed DB; Sprint 6 không thêm bảng. Đăng nhập `parent_a` / `student_a` để xem dashboard ngay dưới phần tài khoản. Dữ liệu thiếu sẽ được ghi rõ, không suy ra điểm/chuyên cần.


**Sprint 5 đã tích hợp:** Thông báo trường/khối/lớp, hội thoại giáo viên–phụ huynh, phiếu hỗ trợ và hộp thông báo đã đọc/chưa đọc. Có Support Desk mới tại **http://127.0.0.1:5177**. Xem [hướng dẫn Sprint 5](docs/SPRINT5_IMPLEMENTATION.md), [kết quả kiểm chứng](docs/SPRINT5_DELIVERY_MANIFEST.md) và [kịch bản nghiệm thu](docs/SPRINT5_ACCEPTANCE.md).

Cập nhật: `pnpm install --frozen-lockfile`, `docker compose exec backend python manage.py migrate --noinput`, `docker compose exec backend python manage.py seed_demo`. Khởi động lại ba Metro với `--clear` để nhận package mới; giữ `.env` API LAN và Expo SDK 58. Support Desk: `pnpm dev:support`, tài khoản `support_a` / `DemoOnly!ChangeMe123`. Nếu dùng Compose LAN, xem lệnh giữ LAN trong hướng dẫn Sprint 5 khi cập nhật CORS.

Luồng demo: `admin_a` hoặc `gvcn_a` lưu nháp → công bố → `parent_a`/`student_a` đọc; `parent_a` nhắn GVCN và tạo yêu cầu hỗ trợ → `support_a` phản hồi/giải quyết/đóng. Chưa có gửi push/email/SMS. Cần nghiệm thu các luồng mới trên điện thoại thật.


**Sprint 4 đã tích hợp:** Giáo viên tạo/sửa nháp, giao/đóng bài và trả nhận xét/điểm bài tập trên Teacher Web/Mobile. Student Mobile lưu/nộp văn bản; Parent Mobile xem tiến độ/phản hồi; GVCN theo dõi lớp ở chế độ chỉ đọc. Điểm bài tập không tự chuyển sang sổ điểm Sprint 3. Xem [phạm vi và kiểm chứng](docs/SPRINT4_DELIVERY_MANIFEST.md), [API](docs/SPRINT4_API.md), [hướng dẫn chạy](docs/SPRINT4_IMPLEMENTATION.md), [nghiệm thu](docs/SPRINT4_ACCEPTANCE.md).

Sau khi cập nhật: `pnpm install --frozen-lockfile` và `docker compose exec backend python manage.py migrate --noinput`. Khởi động lại Expo Teacher vì đã thêm bộ chọn ngày giờ. Giữ nguyên cấu hình API LAN đang dùng. Luồng demo: `gvbm_a` giao bài → `student_a` nộp → `gvbm_a` trả bài → `parent_a` xem phản hồi.

**Sprint 3 đã tích hợp:** Admin tạo/công bố sổ điểm và duyệt điều chỉnh; giáo viên bộ môn nhập/khóa điểm trên Web/Mobile; Parent/Student xem kết quả đã công bố. Xem [phạm vi và kết quả kỹ thuật](docs/SPRINT3_DELIVERY_MANIFEST.md), [API](docs/SPRINT3_API.md), [nghiệm thu](docs/SPRINT3_ACCEPTANCE.md).

Sau cập nhật source, chạy `docker compose exec backend python manage.py migrate --noinput`. Demo: `admin_a` tạo sổ điểm cho lớp/môn → `gvbm_a` nhập và khóa → `admin_a` công bố → `parent_a`/`student_a` xem trên mobile. Đề nghị điều chỉnh thực hiện trên Teacher Web. Các lệnh chạy app và cấu hình LAN bên dưới giữ nguyên.


**Sprint 2 đã tích hợp:** GVCN điểm danh trên Teacher Web/Mobile; phụ huynh gửi/rút đơn nghỉ và xem lịch sử trên Parent Mobile. API hỗ trợ duyệt đơn, khóa phiên và outbox thông báo (chưa gửi push). Xem [phạm vi](docs/SPRINT2_IMPLEMENTATION.md), [API](docs/SPRINT2_API.md) và [kịch bản nghiệm thu](docs/SPRINT2_TEST_PLAN.md).

Chạy `docker compose exec backend python manage.py migrate --noinput` khi cập nhật từ Sprint 1. Teacher Web: `pnpm dev:teacher-web` → http://127.0.0.1:5174 (`gvcn_a`). Mobile: `pnpm dev:teacher` và `pnpm dev:parent` ở hai terminal riêng. Giữ cấu hình LAN đang dùng trong `.env`.

**Sprint 1 đã tích hợp:** Dashboard, năm học, môn học, nhân sự, lớp, học sinh, phân lớp/phân công, phụ huynh và audit trên Admin Web. Xem [phạm vi Sprint 1](docs/SPRINT1_IMPLEMENTATION.md) và [kiểm thử/nghiệm thu](docs/SPRINT1_TEST_PLAN.md). Tài khoản mới chưa có luồng kích hoạt; sửa/lưu trữ học sinh và sửa lớp hiện qua API.

**Nền Sprint 0:** xem [kết quả kiểm chứng](docs/VERIFY.md), [phạm vi Sprint 0](docs/SPRINT0_SCOPE.md) và [API](docs/API.md).

**Mục tiêu:** 1 trường THCS pilot (2 synthetic tenants để test). **Không dùng dữ liệu học sinh thật.**
**Thiết kế:** 3 React Native + Expo apps **tách biệt**, 4 React Web apps, 1 Django REST backend, PostgreSQL.

## Quickstart (Mac M2)

Yêu cầu: Node.js 22.13+, Corepack/pnpm 10, Docker Desktop; iOS Simulator hoặc Android Emulator hoặc Expo Go.

```bash
# 1. Chạy DB + API (synthetic dev only)
docker compose up --build -d
docker compose exec backend python manage.py seed_demo
curl http://127.0.0.1:8000/healthz/

# 2. Khởi tạo JavaScript workspaces
corepack enable
pnpm install --frozen-lockfile
pnpm typecheck
pnpm build:web
pnpm expo:doctor
pnpm build:mobile   # xuất JS/Hermes bundles iOS và Android, không phải APK/IPA
pnpm test:contracts

# 3. Chạy web (mỗi lệnh ở terminal khác)
pnpm dev:admin       # http://localhost:5173
pnpm dev:teacher-web # http://localhost:5174
pnpm dev:support     # http://127.0.0.1:5177
pnpm dev:platform    # http://localhost:5175 (UI shell; no backend API)

# 4. Chạy 3 app điện thoại (mỗi app trên port Metro/terminal riêng)
cp apps/teacher-mobile/.env.example apps/teacher-mobile/.env
cp apps/parent-mobile/.env.example apps/parent-mobile/.env
cp apps/student-mobile/.env.example apps/student-mobile/.env
pnpm dev:teacher
pnpm dev:parent
pnpm dev:student
```

### Điều chỉnh API_URL theo thiết bị
- **iOS Simulator**: `http://127.0.0.1:8000` thường dùng được trên Mac.
- **Android Emulator**: `http://10.0.2.2:8000` (đổi từng `.env`).
- **Điện thoại thật**: `.env` = `http://<IP-LAN-Mac>:8000`; Docker Compose mặc định CHỈ lắng nghe localhost.
  Nếu phải test điện thoại thật, chỉ trên mạng Wi-Fi tin cậy và firewall giới hạn,
  đặt `DJANGO_BIND_IP=<IP-LAN-Mac>` và `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,<IP-LAN-Mac>` và chạy `docker compose -f compose.yaml -f compose.mobile-lan.yaml up --build -d`.
  `!override` yêu cầu Docker Compose 2.24.4+. Cảnh báo: HTTP + demo JWT không an toàn trên mạng không tin cậy.
  Tốt hơn dùng HTTPS tunnel riêng/đường kết nối bảo mật trước khi thử với người dùng ngoài nhóm dev.

**Expo SDK baseline: SDK 58** cho cả Teacher, Parent và Student, tương thích Expo Go SDK 58. Dependency native đã đồng bộ theo Expo (React Native 0.88.0 / React 19.3.0).

Sau nâng SDK, dừng Metro cũ bằng `Ctrl+C` ở từng terminal, rồi chạy từng lệnh trong terminal riêng:

```bash
pnpm dev:teacher --clear
pnpm dev:parent --clear
pnpm dev:student --clear
```

Quét lại QR mới bằng Expo Go. Nếu vẫn báo SDK 57, kiểm tra bạn đã dừng đúng server cũ và mở đúng thư mục dự án. Cài từ Git ở máy khác cần chạy `pnpm install --frozen-lockfile` trước. Development build tùy chỉnh cần build lại sau khi đổi SDK. [Hướng dẫn nâng SDK của Expo](https://docs.expo.dev/workflow/upgrading-expo-sdk-walkthrough/).

## Demo accounts (100% synthetic)
Password cho mọi tài khoản demo: `DemoOnly!ChangeMe123`.
- Teacher app: `gvcn_a` hoặc `gvbm_a`
- Parent app: `parent_a`
- Student app: `student_a`
- Admin Web: `admin_a`
- Teacher Web: `gvcn_a`
- Tenant B có tài khoản tương ứng `*_b`, dùng để kiểm tra cross-tenant isolation.

## Packages
```text
apps/
  admin-web/              React + Vite [API live]
  teacher-web/            React + Vite [API live]
  platform-console/       React + Vite [UI shell only]
  teacher-mobile/         Expo Router [API live]
  parent-mobile/          Expo Router [API live]
  student-mobile/         Expo Router [API live]
packages/
  api-client/             auth / roster / school administration
  design-tokens/          shared color/spacing values
backend/                  Django API, migrations và regression tests
```

## Architectural boundaries
- Shared package code includes types, API client, tokens. **Do not share DOM UI components with React Native.**
- Navigation, screen & branding tách cho 3 app; có thể release độc lập (app IDs placeholder, phải thay khi ra store).
- `Platform Console` là UI shell **không có** platform admin backend / capabilities trong source.
- Backend kiểm tra tenant + membership + teacher assignment / guardian verification / student account.
- CORS cho browser thôi, không thay thế backend authorization.

## Status and next steps
Xem `docs/VERIFY.md` để biết các test đã/chưa chạy và `docs/SPRINT1_GATE.md` cho release gates.
Django migrations đã có trong source; Compose chỉ chạy `migrate`, không tự sinh migrations.
Dependency Python đã pin; pnpm lockfile dùng `--frozen-lockfile` trong CI.

### Kiểm thử lại
```bash
docker compose exec backend python manage.py test apps.academics.tests apps.access.tests
docker compose exec backend python manage.py makemigrations --check --dry-run
python3 scripts/smoke_api.py
```

Nếu máy chưa có `pnpm`, có thể dùng `npm exec --yes --package=pnpm@10.18.3 -- pnpm <lệnh>`.
Ba Metro server dùng port riêng 8081 (Teacher), 8082 (Parent), 8083 (Student).
`seed_demo` chỉ chạy khi `DJANGO_DEBUG=1`; chạy lại không tạo bản ghi trùng hoặc đặt lại mật khẩu account đã tồn tại.

Repository Git riêng đã được khởi tạo trong folder dự án để quản lý source, migrations và lockfile.
CI remote, branch protection, phê duyệt auth production, QA màn hình và smoke test trên thiết bị vẫn là các gate cần đóng riêng (xem VERIFY.md).
Các file Word/PDF v2.0 ban đầu là tài liệu lịch sử; trạng thái hiện tại được cập nhật trong tài liệu Markdown.

Reference docs:
- https://docs.expo.dev/guides/monorepos/
- https://docs.expo.dev/router/introduction/
- https://docs.expo.dev/versions/v58.0.0/
- https://expo.dev/changelog/sdk-58
