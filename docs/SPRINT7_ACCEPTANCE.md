# Sprint 7 — Nghiệm thu và quyết định pilot

Phần kiểm chứng tự động được ghi ở [delivery manifest](SPRINT7_DELIVERY_MANIFEST.md). Các ô dưới đây cần bằng chứng từ thiết bị/môi trường thực và người nghiệm thu. Không đánh dấu PASS chỉ vì backend CI xanh. **Trạng thái pilot: NO-GO cho tới khi đủ các gate bắt buộc.**

Đã có [smoke iOS Teacher/Parent](SPRINT7_IOS_SMOKE.md); Student iOS và cả 3 app Android chưa được xác minh. Không đánh dấu gate thiết bị hoàn tất từ kết quả một phần này.

## Thiết bị và luồng sử dụng

Chạy từng lệnh trong terminal riêng, giữ Expo Go SDK 58 và API LAN hiện có:

```bash
pnpm dev:teacher --clear
pnpm dev:parent --clear
pnpm dev:student --clear
```

Đăng nhập Teacher bằng `gvcn_a`/`gvbm_a`, Parent `parent_a`, Student `student_a`. Dùng mật khẩu demo hiện tại. Admin Web `pnpm dev:admin`; Teacher Web `pnpm dev:teacher-web`; Support `pnpm dev:support`. Tất cả dùng dữ liệu giả lập.

- [ ] **native_ios:** Teacher, Parent, Student khởi chạy, đăng nhập và logout trên iOS. Ghi phiên bản OS/Expo, model thiết bị, commit và ảnh/log.
- [ ] **native_android:** Lặp lại cả 3 app trên Android, ghi cùng metadata. iOS pass không thay cho Android.
- [ ] **journeys_ui:** Thực hiện J01–J10 trong [ma trận](SPRINT7_TEST_MATRIX.md) qua các giao diện; đối chiếu người thực hiện, trạng thái trước/sau, dữ liệu draft/published và tenant B không xem được.
- [ ] **accessibility_network:** Kiểm tra chữ lớn, VoiceOver/TalkBack, focus bàn phím web, lớp 45+ học sinh, mạng yếu/mất mạng/retry/nhấn nhanh, background/resume, token hết hạn, logout và đổi tài khoản/con không hiện dữ liệu cũ.
- [ ] **security_privacy:** Chủ trường/người phụ trách bảo vệ dữ liệu xác minh guardian, quyền truy cập/thu hồi, logging, retention, consent/căn cứ xử lý, quy trình onboarding/khôi phục tài khoản/thiết bị thất lạc; rà soát security và chốt các khoảng trống hiện có. Không tự suy ra đã có legal approval.
- [ ] **backup_restore_rollback:** Người vận hành diễn tập ở môi trường mục tiêu theo [runbook](SPRINT7_OPERATIONS.md), xác nhận integrity, quyền sau restore, rollback code, RPO/RTO. Bản synthetic local là bằng chứng kỹ thuật hỗ trợ.
- [ ] **monitoring_alerts:** Có probe/metrics/alert thật, người nhận và kết quả diễn tập cảnh báo–xử lý–hồi phục.
- [ ] **school_uat:** Chủ dự án và đại diện trường ký nghiệm thu UAT bằng dữ liệu giả lập, xác nhận phạm vi và mọi P0/P1 đã được xử lý.

## Hồ sơ và gate

Giữ file evidence ngoài repo (tránh đưa dữ liệu riêng tư vào Git). Tạo JSON theo ví dụ dưới; có đủ **8 gate** nêu trên. Mỗi `artifact` là đường dẫn tương đối trong thư mục evidence và `sha256` là digest của file đã được người có trách nhiệm duyệt. Có thể dùng một báo cáo tổng hợp với các phần tương ứng. Không dùng dữ liệu fixture unit test làm bằng chứng.

```json
{
  "commit": "FULL_GIT_SHA_BEING_ACCEPTED",
  "open_p0_p1": null,
  "gates": {
    "native_ios": {
      "status": "PENDING",
      "reviewer": "",
      "reviewed_at": "",
      "artifact": "ios-acceptance.pdf",
      "sha256": ""
    }
  }
}
```

Lấy commit bằng `git rev-parse HEAD`, SHA-256 bằng `shasum -a 256 /path/to/artifact`. Khi đã có hồ sơ đúng commit và working tree sạch:

```bash
bash scripts/pilot_release_gate.sh /path/to/evidence/evidence.json
```

Lệnh từ chối khi thiếu file, thiếu PASS/người duyệt/ngày duyệt, digest sai, commit cũ, working tree thay đổi hoặc chưa xác nhận số P0/P1 bằng 0. Khi hồ sơ hợp lệ, nó mới chạy full automation; lỗi bất kỳ bước nào vẫn chặn gate. Công cụ không xác thực danh tính/chữ ký và không tự triển khai hệ thống.

Để chỉ chạy kỹ thuật khi chưa có hồ sơ thủ công: `bash scripts/verify_sprint7.sh --full`. Lệnh này không đưa ra GO pilot.
