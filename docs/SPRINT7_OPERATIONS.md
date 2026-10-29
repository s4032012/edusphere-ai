# Sprint 7 — Runbook vận hành và khôi phục

Phạm vi thực thi hiện tại là Docker development và dữ liệu giả lập. Trước pilot cần môi trường staging/production, chủ vận hành, lịch backup, retention, vị trí lưu được bảo vệ và quyền truy cập được phê duyệt. Không dùng Compose development hiện tại làm cấu hình production.

## Health và cảnh báo

```bash
curl --fail http://127.0.0.1:8000/healthz/
curl --fail http://127.0.0.1:8000/readyz/
docker compose exec -T backend python manage.py migrate --check
```

Liveness kiểm tra process; readiness chỉ kiểm tra kết nối/query DB. Nếu live 200/ready 503, kiểm tra trạng thái DB, network và cấu hình kết nối; không restart liên tục backend để che lỗi DB. Nếu cả hai lỗi, kiểm tra process và port. Khi ready hồi phục, chạy HTTP smoke và đọc dữ liệu theo vai trò trước khi phục vụ lại. Response công khai không chứa exception/DSN.

Người vận hành cần cấu hình và nghiệm thu cảnh báo ở môi trường mục tiêu: probe lỗi liên tiếp, tỷ lệ HTTP 5xx, độ trễ API, DB connection saturation, dung lượng đĩa và tuổi backup gần nhất. Chọn ngưỡng/tần suất theo tải và SLO đã thống nhất; ghi người nhận, thời điểm phát hiện, thời điểm phản hồi và phục hồi. Sprint 7 chưa cài dịch vụ monitoring hay gửi alert ngoài hệ thống.

## Diễn tập tự động an toàn

```bash
python3 scripts/sprint7_recovery_drill.py
docker compose exec -T backend python < scripts/sprint7_probe_drill.py
```

Recovery drill chỉ tạo hai database tạm, không đọc backup hoặc restore đè database demo. So sánh đầy đủ dữ liệu từng bảng ở hai bản, kiểm tra migration và API quyền truy cập. Thất bại cleanup sẽ báo tên database tạm cần xử lý. Không xóa database nào khác.

Khi diễn tập staging: ghi commit, schema/migration trước và sau, thời gian backup/restore, checksum, số bản ghi, kiểm tra quyền truy cập, RPO/RTO đạt hay chưa và người xác nhận. Bản sao synthetic local không chứng minh hệ thống trường sẽ phục hồi trong cùng thời gian.

## Rollback ứng dụng Sprint 7

Sprint 7 không thêm migrations. Khi rollback về release Sprint 6 đã kiểm chứng, giữ nguyên schema và volume PostgreSQL. Dừng rollout, ghi lại lỗi, khôi phục image/source của release đã phê duyệt, chạy `migrate --check`, health/readiness và smoke theo vai trò. Dùng đúng cấu hình LAN/ingress trước đó; không dùng `docker compose down -v`, reset DB hay `migrate ... zero` trên database đang dùng.

Với sprint tương lai có thay đổi schema, phải kiểm tra tương thích code cũ/schema mới và rollback trên bản sao trước; nếu không tương thích, phục hồi backup vào database riêng, xác minh rồi mới chuyển kết nối. Không coi migrate ngược là không mất dữ liệu.

## Sự cố quyền truy cập

Thu hồi guardian link/teacher assignment/membership đang có hiệu lực; kiểm tra lại bằng JWT còn hạn. Test tự động bảo vệ các trường hợp này. Quy trình khóa thiết bị thất lạc, token revocation từng phiên, onboarding và password recovery còn là việc phải nghiệm thu riêng. Log chỉ giữ metadata cần điều tra; không sao chép token, mật khẩu, nội dung tin nhắn/bài làm hay lý do nghỉ vào issue công khai.
