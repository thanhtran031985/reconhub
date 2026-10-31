#!/usr/bin/env bash
# ==============================================================================
# ReconHub — Linux Systemd Installation Script
# Yêu cầu: Quyền root hoặc sudo
# ==============================================================================

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
   echo "LỖI: Vui lòng chạy script này với quyền root hoặc sudo: sudo ./install.sh"
   exit 1
fi

APP_DIR="${APP_DIR:-/opt/reconhub}"
LOG_DIR="${LOG_DIR:-/var/log/reconhub}"
SYSTEMD_DIR="/etc/systemd/system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================================"
echo " ReconHub — Cài đặt Dịch vụ trên Linux (Systemd)"
echo " Thư mục ứng dụng: $APP_DIR"
echo " Thư mục logs:     $LOG_DIR"
echo "======================================================"

# 1. Tạo user và group hệ thống reconhub nếu chưa có
if ! id -u reconhub >/dev/null 2>&1; then
    echo "-> Đang tạo system user 'reconhub'..."
    useradd -r -s /usr/sbin/nologin -d "$APP_DIR" -c "ReconHub Service Account" reconhub
else
    echo "-> User 'reconhub' đã tồn tại."
fi

# 2. Tạo thư mục log và phân quyền
echo "-> Tạo thư mục log: $LOG_DIR..."
mkdir -p "$LOG_DIR"
chown -R reconhub:reconhub "$LOG_DIR"
chmod 750 "$LOG_DIR"

# 3. Phân quyền thư mục ứng dụng
if [[ -d "$APP_DIR" ]]; then
    echo "-> Thiết lập quyền sở hữu cho $APP_DIR..."
    chown -R reconhub:reconhub "$APP_DIR"
fi

# 4. Sao chép các file unit systemd
echo "-> Sao chép systemd service units..."
cp "$SCRIPT_DIR/reconhub-web.service" "$SYSTEMD_DIR/"
cp "$SCRIPT_DIR/reconhub-worker.service" "$SYSTEMD_DIR/"
cp "$SCRIPT_DIR/reconhub-backup.service" "$SYSTEMD_DIR/"
cp "$SCRIPT_DIR/reconhub-backup.timer" "$SYSTEMD_DIR/"

chmod 644 "$SYSTEMD_DIR/reconhub-"*

# 5. Reload systemd daemon
echo "-> Reloading systemd..."
systemctl daemon-reload

# 6. Kích hoạt và khởi chạy các dịch vụ
echo "-> Kích hoạt tự khởi động cho các dịch vụ..."
systemctl enable reconhub-web.service
systemctl enable reconhub-worker.service
systemctl enable reconhub-backup.timer

echo "-> Khởi động các dịch vụ..."
systemctl restart reconhub-web.service
systemctl restart reconhub-worker.service
systemctl restart reconhub-backup.timer

echo ""
echo "======================================================"
echo " Cài đặt hoàn tất!"
echo " Trạng thái dịch vụ:"
systemctl status reconhub-web.service --no-pager || true
systemctl status reconhub-worker.service --no-pager || true
systemctl status reconhub-backup.timer --no-pager || true
echo "======================================================"

