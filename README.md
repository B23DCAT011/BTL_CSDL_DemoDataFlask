# LapTop Shop Management System

Hệ thống quản lý cửa hàng laptop với Flask và SQL Server.

## Cài đặt

### 1. Cài đặt Python packages

```bash
pip install -r requirements.txt
```

### 2. Cấu hình Database

Copy file `.env.example` thành `.env` và điền thông tin database:

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

-  Quản lý đơn hàng
-  Quản lý khách hàng
-  Tìm kiếm nhân viên
-  Quản lý sản phẩm laptop

## Cấu trúc thư mục

```
LapTopDemo/
├── app.py                 
├── .env                   
├── .env.example            
├── .gitignore           
├── requirements.txt        
├── README.md             
└── templates/             
    ├── index.html
    ├── LapTop.html
    ├── taoDonHang.html
    ├── taoKhachHang.html
    └── timKiemNhanVien.html
```

