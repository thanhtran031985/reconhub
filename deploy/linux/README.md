# Hướng dẫn triển khai ReconHub trên Linux Server

Tài liệu hướng dẫn cài đặt và vận hành ReconHub trên Linux (Ubuntu Server 22.04/24.04 LTS hoặc RHEL/Rocky Linux 8/9) chạy trực tiếp Python với **Gunicorn**, **Systemd** và **Nginx** reverse proxy (không sử dụng Docker).

---

## 1. Yêu cầu môi trường
- Hệ điều hành: Ubuntu 22.04/24.04 LTS hoặc RHEL/Rocky Linux 9 64-bit.
- Python: 3.12 (cài đặt qua `deadsnakes` PPA trên Ubuntu hoặc qua `uv`).
- Quản lý gói: `uv` (tải bằng `curl -LsSf https://astral.sh/uv/install.sh | sh`).
- Web server reverse proxy: `nginx`.
- Kết nối VPN: OpenVPN hoặc StrongSwan kết nối vào mạng Oracle Server.

---

## 2. Quy trình cài đặt

### Bước 2.1: Chuẩn bị thư mục và mã nguồn
```bash
# Tạo thư mục ứng dụng chuẩn
sudo mkdir -p /opt/reconhub
sudo chown -R $USER:$USER /opt/reconhub

# Clone mã nguồn
git clone https://github.com/thanhtran031985/reconhub.git /opt/reconhub
cd /opt/reconhub

# Đồng bộ môi trường ảo bao gồm gói sản xuất (gunicorn)
uv sync --extra prod

# Cấu hình biến môi trường
cp .env.example .env
nano .env

# Chạy migration schema database
uv run poe db-migrate

# Tạo tài khoản quản trị viên ban đầu
uv run python -m app.cli create-admin --username admin --password "MatKhauManh123" --fullname "Quản Trị Viên"
```

### Bước 2.2: Cài đặt Systemd Services
Chạy script cài đặt tự động bằng quyền `sudo`:
```bash
cd /opt/reconhub/deploy/linux
sudo chmod +x install.sh
sudo ./install.sh
```

Script sẽ tự động:
1. Tạo system user `reconhub` không có shell đăng nhập.
2. Tạo thư mục `/var/log/reconhub/` phân quyền thích hợp.
3. Đăng ký các dịch vụ `reconhub-web.service`, `reconhub-worker.service`, và `reconhub-backup.timer`.
4. Kích hoạt tự khởi động khi boot máy và khởi chạy dịch vụ.

### Bước 2.3: Cấu hình Nginx Reverse Proxy
```bash
sudo cp /opt/reconhub/deploy/linux/nginx.conf /etc/nginx/sites-available/reconhub
sudo ln -s /etc/nginx/sites-available/reconhub /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 3. Quản lý và vận hành trên Linux

### Kiểm tra trạng thái dịch vụ
```bash
sudo systemctl status reconhub-web.service
sudo systemctl status reconhub-worker.service
sudo systemctl status reconhub-backup.timer
```

### Khởi động / Dừng / Khởi động lại
```bash
# Khởi động lại Web
sudo systemctl restart reconhub-web.service

# Khởi động lại Worker
sudo systemctl restart reconhub-worker.service

# Dừng dịch vụ khi bảo trì
sudo systemctl stop reconhub-worker.service
sudo systemctl stop reconhub-web.service
```

### Giám sát log thời gian thực
```bash
# Xem log qua journalctl
sudo journalctl -u reconhub-web.service -f
sudo journalctl -u reconhub-worker.service -f

# Xem file log
tail -f /var/log/reconhub/access.log
tail -f /var/log/reconhub/error.log
tail -f /var/log/reconhub/worker.log
```

### Chạy sao lưu thủ công
```bash
sudo systemctl start reconhub-backup.service
# Hoặc chạy trực tiếp qua cli:
sudo -u reconhub /opt/reconhub/.venv/bin/python -m app.cli backup
```

