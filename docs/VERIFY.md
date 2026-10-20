# Kết quả kiểm chứng Sprint 0 — 2026-10-18

Phần nền kỹ thuật đã được triển khai và kiểm thử local với dữ liệu giả lập. Chưa nghiệm thu toàn bộ các gate cần UI/thiết bị, repository remote hoặc phê duyệt của chủ dự án. Không coi kết quả build bundle là chạy thành công trên điện thoại.

## Đã chạy thành công

| Kiểm tra | Kết quả thực thi |
| --- | --- |
| Cài JavaScript | `pnpm install --frozen-lockfile` thành công; pnpm 10.18.3, Node 22.19.0 |
| TypeScript | 6/6 app typecheck thành công; shared API được kiểm tra qua imports |
| Web builds | Admin Portal, Teacher Workspace, Platform Console: 3/3 Vite production builds |
| Expo dependency check | `expo install --check` thành công cho 3 app, SDK 57, RN 0.86.3 |
| Mobile bundle | `pnpm build:mobile`: 3/3 app xuất cả iOS và Android Hermes bundle |
| API client | 7/7 test thực thi: login, headers, tenant, 401, lỗi server/network, role filter, invalidation |
| Backend SQLite | 32/32 test (22 API + 10 policy), Python 3.14.2 |
| Backend PostgreSQL | 32/32 test trên PostgreSQL 17, cả host Python 3.14 và container Python 3.13 |
| Docker Compose | DB healthy, API build/start/migrate thành công, Django check không lỗi |
| Migrations | 4 migration files trong source; `makemigrations --check --dry-run`: No changes detected |
| Demo seed | Chạy hai lần thành công; hai tenant và 10 account, không tạo trùng |
| HTTP smoke | `python3 scripts/smoke_api.py`: 10 account login/me/roster, cross-tenant/detail denial, missing/invalid tenant, CORS preflight |

Các test regression bao gồm expired JWT, membership revocation với token cũ, guardian verification, student chỉ thấy mình, giáo viên bộ môn không nhận ngày sinh, API write trái tenant, malformed UUID, duplicate không ghi audit và write hợp lệ có audit.

## Kiểm tra thủ công do người dùng xác nhận

Người dùng xác nhận trên web: tài khoản admin và hai tài khoản giáo viên (GVCN, GVBM) đều đăng nhập và xem được danh sách học sinh. Đây là kiểm tra luồng thành công; chưa xác nhận thủ công việc loại trừ học sinh ngoài quyền, đăng nhập sai vai trò, đăng xuất hay hết hạn phiên.

Người dùng tiếp tục xác nhận “work oke hết r” sau khi sửa kết nối mobile: ba file `.env` dùng IP LAN của Mac, API nhận kết nối ở localhost và IP Wi-Fi. Ghi nhận luồng sử dụng mobile đã hoạt động theo phản hồi người dùng; chưa có kết quả riêng từng app/role cho các ca sai quyền, logout, expiry hoặc SecureStore. Health endpoint đã được kiểm tra thành công từ Mac qua cả hai địa chỉ.

## Các kiểm tra và phê duyệt còn lại

- QA giao diện đầy đủ: đã có xác nhận luồng web ở trên; công cụ browser không có surface kết nối, thử native Chrome bị lỗi macOS ScreenCaptureKit `-3811` (capture failure). Đã rà source về labels, loading/error, focus outline và table overflow; chưa chứng nhận accessibility hay layout qua screenshot.
- Kiểm tra mobile chi tiết: sai vai trò, phạm vi học sinh, SecureStore sau logout, expiry, background/resume, keyboard/screen reader; ghi thiết bị/OS và kết quả từng app. Phản hồi hoạt động chung chưa thay thế các ca kiểm thử này.
- EAS APK/IPA, ký ứng dụng, App Store/Google Play: chưa có project/signing setup.
- GitHub: private repository `s4032012/edusphere-ai`; main Sprint 0 CI [run 39194838288](https://github.com/s4032012/edusphere-ai/actions/runs/39194838288) thành công. Branch protection chưa bật: API trả 403 do gói tài khoản/repository private. Sprint 1 có kết quả riêng trong [SPRINT1_TEST_PLAN.md](SPRINT1_TEST_PLAN.md).
- Đối chiếu Phase1 SQL: file SQL không có trong folder. Đã đối chiếu ORM với các entity nền của report, ghi phần còn thiếu trong SPRINT0_SCOPE.md.
- Chủ dự án phê duyệt auth production; trường phê duyệt pilot, nghiệp vụ và dữ liệu thật.

## Các giới hạn còn giữ có chủ đích

JWT demo chưa refresh/revoke server-side; Platform Console chỉ là preview; roster giới hạn 200; chưa có RLS/composite tenant FK, nghiệp vụ điểm/chuyên cần/AI hay production deployment. `healthz` là liveness, không xác minh database.

Cài pnpm có cảnh báo subdependency `uuid@7` deprecated và script `esbuild` bị bỏ qua; Vite builds vẫn thành công với binary được cài. Không chạy audit production hoặc tuyên bố không có vulnerability.

## Chạy lại

```bash
pnpm install --frozen-lockfile
pnpm test:contracts
pnpm typecheck
pnpm build:web
pnpm expo:doctor
pnpm build:mobile
docker compose up --build -d
docker compose exec backend python manage.py seed_demo
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend python manage.py test apps.academics.tests apps.access.tests
python3 scripts/smoke_api.py
```

Bộ smoke HTTP yêu cầu dataset seed nguyên bản và API local; không dùng để xác nhận database đã thêm dữ liệu nghiệp vụ. Tránh chạy liên tiếp quá nhanh vì login có anonymous rate limit.
