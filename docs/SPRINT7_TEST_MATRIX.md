# Sprint 7 — Ma trận kiểm chứng

| Mã | Luồng | Bằng chứng tự động | Còn nghiệm thu UI/device |
|---|---|---|---|
| J01 | Admin tạo năm/lớp/môn/staff/học sinh/phân công/enrollment/guardian, xác minh | `test_j01_school_setup_and_verified_guardian` | Thao tác Admin Web; onboarding account mới |
| J02 | GVCN lưu nháp/nộp; dashboard chỉ thấy sau nộp | `test_j02_attendance_published_into_dashboard` | Teacher và Parent Mobile |
| J03 | Parent xin nghỉ, GVCN duyệt, inbox + chuyên cần cập nhật | `test_j03_leave_decision_and_inbox` | Mạng yếu/nhấn lại |
| J04 | Nhập điểm 0, khóa, Admin công bố; Parent/Student thấy | `test_j04_grade_publication_and_zero_score` | Web + hai mobile |
| J05 | Giao/nộp/trả bài; retry bị kiểm soát; không ghi sổ điểm | `test_j05_homework_submission_return_and_dashboard` | Nhập văn bản dài/đổi mạng |
| J06 | Hội thoại đúng phân công, chống trùng, thu hồi chặn đọc | `test_j06_messages_retry_and_assignment_revocation` | Teacher/Parent đang mở màn hình |
| J07 | Nháp thông báo kín, công bố đúng lớp, đọc cập nhật | `test_j07_announcement_publication_and_read_receipts` | Admin/Teacher/Parent/Student |
| J08 | Parent ticket, Support trả lời/resolve, tin nhắn riêng kín | `test_j08_support_can_resolve_ticket_but_not_read_private_messages` | Support Web + Parent Mobile |
| J09 | Dashboard/tóm tắt deterministic, không gửi provider/mark read | `test_j09_preview_is_deterministic_and_read_only` | Chuyển con, chữ lớn |
| J10 | Revoke khi JWT còn hạn, expired JWT bị từ chối | `test_j10_revocation_and_expired_token_across_modules` | Logout/cache/background |

Các test trên nằm trong `backend/apps/regression/tests/test_integration_journeys.py`. Test lớp 45 học sinh xác nhận roster và scope dashboard, không phải load benchmark. Bộ 12 test trong `test_security_journeys.py` kiểm tra tenant/vai trò/quan hệ; 7 test `test_operations.py` kiểm tra probes và seed. Các suite Sprint 0–6 tiếp tục bao phủ concurrency, IDOR, dữ liệu nháp, notification live policy và query growth.

| Lớp kiểm tra | Cách chạy |
|---|---|
| Source + pure rules + contracts + gate unit tests | `bash scripts/verify_sprint7.sh` |
| PostgreSQL + all app builds + runtime/recovery | `bash scripts/verify_sprint7.sh --full` |
| HTTP read-only | `python3 scripts/sprint7_smoke.py` |
| DB connection failure | `docker compose exec -T backend python < scripts/sprint7_probe_drill.py` |
| Synthetic backup/restore | `python3 scripts/sprint7_recovery_drill.py` |
| Pilot evidence + full automation | `bash scripts/pilot_release_gate.sh /path/to/evidence.json` |

Không chạy các lệnh test cùng lúc nếu dùng chung database `test_edusphere`. Khi thay code, ghi lại commit và chạy nhóm test chịu ảnh hưởng; CI chạy toàn bộ trên commit được push.
