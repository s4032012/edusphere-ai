# EduSphere AI · Sprint 1 — School Administration Core

**Sprint 1 đã tích hợp:** Dashboard, năm học, môn học, nhân sự, lớp, học sinh, phân lớp/phân công, phụ huynh và audit trên Admin Web. Xem [phạm vi Sprint 1](docs/SPRINT1_IMPLEMENTATION.md) và [kiểm thử/nghiệm thu](docs/SPRINT1_TEST_PLAN.md). Tài khoản mới chưa có luồng kích hoạt; sửa/lưu trữ học sinh và sửa lớp hiện qua API.

**Nền Sprint 0:** xem [kết quả kiểm chứng](docs/VERIFY.md), [phạm vi Sprint 0](docs/SPRINT0_SCOPE.md) và [API](docs/API.md).

**Mục tiêu:** 1 trường THCS pilot (2 synthetic tenants để test). **Không dùng dữ liệu học sinh thật.**
**Thiết kế:** 3 React Native + Expo apps **tách biệt**, 3 React Web apps, 1 Django REST backend, PostgreSQL.

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

**Expo SDK baseline: SDK 57**; SDK 58 phát hành 15/10/2026, cân nhắc upgrade sau khi kiểm tra Expo Go và library compatibility.

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
- https://docs.expo.dev/versions/v57.0.0/
- https://expo.dev/changelog/sdk-58
