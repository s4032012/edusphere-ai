# Sprint 0 v1 → v2 Migration Delta

| Thành phần | v1 | v2 |
|---|---|---|
| Admin Web | Vue 3/Vite | React/TypeScript/Vite — THAY |
| Teacher Web | chưa tách | React/TypeScript/Vite — MỚI |
| Platform Console | không có | React shell, KHÔNG CÓ platform API — MỚI |
| Teacher Mobile | không có | Expo Router app riêng — MỚI |
| Parent Mobile | không có | Expo Router app riêng — MỚI |
| Student Mobile | không có | Expo Router app riêng — MỚI |
| Shared frontend packages | không có | API client và design tokens — MỚI |
| Monorepo | frontend + backend | pnpm workspace + Turborepo — MỚI |
| Django backend, ORM, policy tests | prototype v1 | giữ nguyên để đảm bảo không vô tình sửa logic — GIỮ |
| CORS | :5173 | :5173 / :5174 / :5175 — CẬP NHẬT |
| Docker Compose | backend, DB, Vue | backend, DB; JS chạy pnpm local — CẬP NHẬT |
| CI | Python + Vue | Python + web + 3 Expo typecheck — CẬP NHẬT |

Vẫn chưa hoàn thành: committed migrations, Postgres CI, OAuth/OIDC/BFF, token refresh/revocation, RLS,
strict backend role semantics cho toàn bộ School Admin / Principal và Platform Admin, operational dashboards,
EAS release pipeline, production deployments, end-to-end tests.

## Bổ sung hoàn thiện Sprint 0
- Tạo migrations identity/schools/academics; bỏ makemigrations khi start Compose.
- Pin Python dependencies, tạo pnpm lockfile; CI PostgreSQL + frozen install + bundle mobile.
- Sửa UUID đầu vào, duplicate constraint thành 400, audit transaction, CORS tenant header.
- Sửa classroom scope: giáo viên thấy lớp được giao dù chưa có học sinh; không suy ra quyền lớp khác từ enrollment của học sinh.
- Timer JWT expiry, xử lý 401, xóa state, chặn response cũ khi đổi trường/logout trên web/mobile.
- Sửa TypeScript 6/Vite types; đồng bộ Expo/RN/Metro; cổng Metro riêng.
- Thay test tìm chuỗi bằng 7 test thực thi API client; mở rộng backend lên 32 test; thêm HTTP smoke script.
- Chặn seed ở môi trường không DEBUG; không reset password khi seed lại.
- Trạng thái hiện tại xem VERIFY.md; các phần “chưa hoàn thành” phía trên mô tả bản kit gốc.
