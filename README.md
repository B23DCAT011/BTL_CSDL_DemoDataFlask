# LapTop Shop Management System

Hệ thống quản lý cửa hàng laptop với Flask và SQL Server.

## Cài đặt

### 1. Cài đặt Python packages

```bash
pip install -r requirements.txt
```

### 2. Cấu hình Database

Copy file `.env.example` thành `.env` và điền thông tin database của bạn:

```bash
copy .env.example .env
```

Sau đó chỉnh sửa file `.env`:

```
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_SERVER=YOUR_SERVER_NAME\SQLEXPRESS
DB_DATABASE=DataLapTopShop
DB_UID=sa
DB_PWD=your_password
```

### 3. Chạy ứng dụng

```bash
python app.py
```

Ứng dụng sẽ chạy tại: `http://127.0.0.1:5000`

## Tính năng

- ✅ Quản lý đơn hàng
- ✅ Quản lý khách hàng
- ✅ Tìm kiếm nhân viên
- ✅ Quản lý sản phẩm laptop

## Cấu trúc thư mục

```
LapTopDemo/
├── app.py                  # File chính của ứng dụng
├── .env                    # File cấu hình (không commit)
├── .env.example            # File cấu hình mẫu
├── .gitignore             # Git ignore file
├── requirements.txt        # Python dependencies
├── README.md              # File này
└── templates/             # HTML templates
    ├── index.html
    ├── LapTop.html
    ├── taoDonHang.html
    ├── taoKhachHang.html
    └── timKiemNhanVien.html
```

## Lưu ý bảo mật

- ⚠️ **KHÔNG** commit file `.env` lên Git
- ⚠️ Luôn sử dụng file `.env.example` làm template
- ⚠️ Đổi mật khẩu database mặc định trong production
