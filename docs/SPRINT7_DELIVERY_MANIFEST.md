# Sprint 7 — Delivery manifest

Ngày kiểm chứng: 29/10/2026. Baseline: Sprint 6 `b932f8d`. Branch `sprint-7/stabilization-integration`. Report/kit gốc chỉ làm đầu vào; không thay thế code/migrations/dependencies đã kiểm chứng của các sprint trước.

## Phạm vi bàn giao

Health/readiness, PostgreSQL connection timeout, regression suite 30 tests, scripts source/full/release gates, read-only HTTP smoke, lỗi kết nối thật trong tiến trình riêng, synthetic backup/restore, cập nhật CI và tài liệu nghiệm thu/vận hành. Expo SDK vẫn là 58, có đồng bộ bản vá theo compatibility check. Không có migrations mới hoặc chức năng AI.

## Kết quả

| Kiểm tra | Kết quả |
|---|---|
| Django check, migration drift, migration applied | PASS; không có schema mới |
| Full PostgreSQL suite | 265/265 PASS, gồm 30 test Sprint 7; lần cuối 116.883 giây |
| Pure Python rules (nằm trong full suite) | 48/48 PASS |
| Python release/smoke gate tests | 10/10 PASS |
| Source safeguard checks | 8/8 PASS |
| API client contracts | 27/27 PASS |
| Native JSX guard + regression | PASS + 2/2 PASS |
| Node 20 negative check | Bị chặn đúng với `ERR_PNPM_UNSUPPORTED_ENGINE` |
| Frozen lockfile | PASS |
| TypeScript / web / mobile | PASS 7 app typechecks, 4 web builds, cả 3 app export JS/Hermes iOS + Android trên dependency cuối |
| Expo compatibility | PASS cả 3 app sau đồng bộ SDK 58 patches |
| HTTP live smoke | PASS 7 tài khoản, 2 tenant, dashboards, teacher rosters, support, role/tenant/anonymous denials |
| Real DB connection failure | PASS ready 200 → 503 → 200; live 200, không stop DB service |
| Backup/restore synthetic | PASS 36 bảng khớp SHA-256; reapply migrations và quyền parent/cross-tenant sau restore; lần cuối 21.8 giây trên dữ liệu nhỏ |
| Pilot gate thiếu hồ sơ | NO-GO, exit 2 đúng kỳ vọng |
| iOS UI | Teacher/Parent smoke đã quan sát trước bản vá RN cuối; Student chưa xác minh, xem [biên bản](SPRINT7_IOS_SMOKE.md) |
| Android UI | NOT RUN; không có SDK/emulator tại máy kiểm thử |

Bản dependency cuối: Expo 58.0.21, Constants 58.0.14, Linking 58.0.15, Router 58.0.28, React Native + Metro config 0.88.1; React 19.3.0. Giữ SDK 58. Node tối thiểu 22.13; `.nvmrc` ghi 22.19.0.

Các bước runtime/build cuối được chạy tiếp sau khi compatibility metadata yêu cầu bản vá RN. Không gọi lần chạy gate đã dừng ở dependency check là PASS; ghi riêng kết quả từng bước và CI của commit cuối trong PR. Migrations/lockfile đã có từ baseline, không sinh lại bằng bootstrap của kit.

## Những mục chưa thể chốt bằng automation

- Teacher/Parent/Student trên iOS và Android, E2E giao diện, accessibility và mạng yếu.
- Security/privacy review, account onboarding/recovery/lost-device/session lifecycle đầy đủ.
- Monitoring/alert và recovery/RPO/RTO ở môi trường mục tiêu.
- P0/P1 review và school UAT có người ký.

**Pilot vẫn NO-GO** cho tới khi các gate ở [acceptance](SPRINT7_ACCEPTANCE.md) có bằng chứng. Không gọi JS/Hermes export là native binary hoặc device test.
