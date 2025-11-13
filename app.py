from flask import Flask, jsonify, render_template, request
import pyodbc
import datetime
import os
from dotenv import load_dotenv

# Load environment variables từ file .env
load_dotenv()

app = Flask(__name__)


def get_db_connection():
    """Tạo kết nối đến database sử dụng thông tin từ .env"""
    driver = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
    server = os.getenv('DB_SERVER', 'localhost')
    database = os.getenv('DB_DATABASE', 'DataLapTopShop')
    uid = os.getenv('DB_UID', 'sa')
    pwd = os.getenv('DB_PWD', '')

    conn = pyodbc.connect(
        f'DRIVER={{{driver}}};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={uid};'
        f'PWD={pwd}'
    )
    return conn


@app.route('/')
def check_connection():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        return render_template('index.html', db_status = True)
    except Exception as e:
        return render_template('index.html', db_status = False, message=f"Connection failed: {str(e)}")


@app.route('/LapTop')
def laptop_list():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Laptop")

        columns = [column[0] for column in cursor.description]

        laptops = []
        for row in cursor.fetchall():
            laptops.append(dict(zip(columns, row)))

        conn.close()
        return render_template('LapTop.html', laptops=laptops)
    except Exception as e:
        return render_template('LapTop.html', laptops=[], message=f"Error fetching data: {str(e)}")

@app.route('/add_DonHang', methods=['GET'])
def add_order_form():
    return render_template('taoDonHang.html')

@app.route('/api/get_gia_sanpham/<int:maSP>', methods=['GET'])
def get_gia_sanpham(maSP):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT MaSP, TenSP, GiaBan, TonKho FROM Laptop WHERE MaSP = ?", (maSP,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return jsonify({
                "status": "success",
                "MaSP": result[0],
                "TenSP": result[1],
                "GiaBan": float(result[2]) if result[2] else 0,
                "TonKho": result[3]
            }), 200
        else:
            return jsonify({"status": "error", "message": "Không tìm thấy sản phẩm"}), 404

    except Exception as e:
        print("Lỗi:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/add_DonHang', methods=['POST'])
def add_DonHang():
    data = request.get_json()

    MaKH = data.get('MaKH')
    MaNV = data.get('MaNV')
    NgayGiao = data.get('NgayGiao')
    TrangThaiXuLy = data.get('TrangThaiXuLy')
    GhiChu = data.get('GhiChu', '')
    ChiTiet = data.get('ChiTiet', [])



    if not MaKH or not MaNV or not NgayGiao or not TrangThaiXuLy or not ChiTiet:
        return jsonify({"status": "error", "message": "Thiếu thông tin bắt buộc"}), 400


    valid_statuses = ['Chưa xử lý', 'Đang giao', 'Hoàn tất']
    if TrangThaiXuLy not in valid_statuses:
        return jsonify({"status": "error", "message": f"Trạng thái không hợp lệ. Phải là: {valid_statuses}"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        ThoiGianTao = datetime.datetime.now()
        TongTien = sum(item['SoLuong'] * item['GiaBan'] for item in ChiTiet)


        insert_donhang = """
            INSERT INTO DonHang (MaKH, MaNV, NgayGiao, ThoiGianTao, TrangThaiXuLy, TongTien, GhiChu)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        cursor.execute(insert_donhang, (MaKH, MaNV, NgayGiao, ThoiGianTao, TrangThaiXuLy, TongTien, GhiChu))


        conn.commit()


        cursor.execute("""
            SELECT TOP 1 MaDH
            FROM DonHang
            WHERE MaKH = ? AND MaNV = ? AND TongTien = ?
            ORDER BY ThoiGianTao DESC
        """, (MaKH, MaNV, TongTien))

        result = cursor.fetchone()

        if result is None:
            raise Exception("Không thể lấy mã đơn hàng vừa tạo")

        new_order_id = int(result[0])


        insert_ct = "INSERT INTO ChiTietDonHang (MaDH, MaSP, SoLuong, GiaBan) VALUES (?, ?, ?, ?)"
        for item in ChiTiet:
            cursor.execute(insert_ct, (new_order_id, item['MaSP'], item['SoLuong'], item['GiaBan']))

        conn.commit()
        conn.close()

        print(f"✅ Tạo đơn hàng thành công! MaDH: {new_order_id}")
        return jsonify({"status": "success", "MaDH": new_order_id, "TongTien": TongTien}), 201

    except Exception as e:
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        print("Lỗi:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/add_KhachHang', methods=['GET'])
def add_KhachHang_form():
    return render_template('taoKhachHang.html')

@app.route('/api/add_KhachHang', methods=['POST'])
def add_KhachHang():
    data = request.get_json()

    HoTen = data.get('HoTen')
    GioiTinh = data.get('GioiTinh')
    NgaySinh = data.get('NgaySinh')
    SDT = data.get('SDT')
    DiaChi = data.get('DiaChi')
    TrangThai = data.get('TrangThai')

    if not HoTen or not SDT:
        return jsonify({"status": "error", "message": "Họ tên và số điện thoại là bắt buộc"}), 400


    valid_genders = ['Nam', 'Nu', 'Khac', None]
    if GioiTinh not in valid_genders:
        return jsonify({"status": "error", "message": "Giới tính không hợp lệ"}), 400


    valid_statuses = ['Active', 'Inactive']
    if TrangThai not in valid_statuses:
        return jsonify({"status": "error", "message": "Trạng thái không hợp lệ"}), 400

    print(f"DEBUG - Adding customer: {data}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO KhachHang (HoTen, GioiTinh, NgaySinh, SDT, DiaChi, TrangThai)
            VALUES (?, ?, ?, ?, ?, ?);
        """

        cursor.execute(insert_query, (HoTen, GioiTinh, NgaySinh, SDT, DiaChi, TrangThai))
        conn.commit()


        cursor.execute("SELECT MaKH FROM KhachHang WHERE SDT = ?", (SDT,))
        result = cursor.fetchone()

        if result is None:
            raise Exception("Không thể lấy mã khách hàng vừa tạo")

        new_customer_id = int(result[0])
        conn.close()

        print(f"✅ Thêm khách hàng thành công! MaKH: {new_customer_id}")
        return jsonify({
            "status": "success",
            "MaKH": new_customer_id,
            "HoTen": HoTen
        }), 201

    except pyodbc.IntegrityError as e:
        if 'UNIQUE' in str(e):
            return jsonify({"status": "error", "message": "Số điện thoại đã tồn tại"}), 400
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        print("Lỗi:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/search_NhanVien', methods=['GET'])
def search_employee_page():
    return render_template('timKiemNhanVien.html')

@app.route('/api/search_employees', methods=['GET'])
def search_employees():
    search_term = request.args.get('q', '').strip()

    if not search_term:
        return jsonify({"status": "error", "message": "Thiếu từ khóa tìm kiếm"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Tìm kiếm theo SĐT hoặc Tên (hỗ trợ tìm gần đúng)
        # Sử dụng LIKE với % để tìm kiếm chứa chuỗi con
        search_pattern = f'%{search_term}%'

        query = """
            SELECT
                nv.MaNV,
                nv.HoTen,
                nv.GioiTinh,
                nv.Email,
                nv.SDT,
                nv.TrangThai,
                nv.LuongCoBan,
                nv.TenChucVu
            FROM NhanVien nv
            WHERE nv.SDT LIKE ?
               OR nv.HoTen LIKE ?
               OR nv.HoTen COLLATE Latin1_General_CI_AI LIKE ?
            ORDER BY nv.TrangThai DESC, nv.HoTen ASC
        """

        cursor.execute(query, (search_pattern, search_pattern, search_pattern))
        rows = cursor.fetchall()
        conn.close()
        employees = []
        for row in rows:
            employees.append({
                'MaNV': row[0],
                'HoTen': row[1],
                'GioiTinh': row[2],
                'Email': row[3],
                'SDT': row[4],
                'TrangThai': row[5],
                'LuongCoBan': float(row[6]) if row[6] else None,
                'TenChucVu': row[7]
            })

        return jsonify({
            "status": "success",
            "data": employees,
            "count": len(employees)
        }), 200

    except Exception as e:
        print("Lỗi tìm kiếm:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'True') == 'True'
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', '5000'))
    
    app.run(debug=debug_mode, host=host, port=port)
