from flask import Flask, jsonify, render_template, request
import pyodbc
import datetime
import os
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)


def get_db_connection():
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

        cursor.execute("SELECT MaSP, TenSP, GiaBan, Kho FROM Laptop WHERE MaSP = ?", (maSP,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return jsonify({
                "status": "success",
                "MaSP": result[0],
                "TenSP": result[1],
                "GiaBan": float(result[2]) if result[2] else 0,
                "Kho": result[3]
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

        for item in ChiTiet:
            maSP = item.get('MaSP')
            soLuongDat = item.get('SoLuong')
            
            cursor.execute("SELECT TenSP, Kho FROM Laptop WHERE MaSP = ?", (maSP,))
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return jsonify({
                    "status": "error",
                    "message": f"Sản phẩm với mã {maSP} không tồn tại"
                }), 400
            
            tenSP = result[0]
            kho = result[1]
            
            if kho < soLuongDat:
                conn.close()
                return jsonify({
                    "status": "error",
                    "message": f"Sản phẩm '{tenSP}' không đủ trong kho. Hiện có: {kho}, yêu cầu: {soLuongDat}"
                }), 400

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
        update_kho = "UPDATE Laptop SET Kho = Kho - ? WHERE MaSP = ?"

        for item in ChiTiet:

            cursor.execute(insert_ct, (new_order_id, item['MaSP'], item['SoLuong'], item['GiaBan']))

            cursor.execute(update_kho, (item['SoLuong'], item['MaSP']))

        conn.commit()
        conn.close()

        print(f" Tạo đơn hàng thành công! MaDH: {new_order_id}")
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

        print(f" Thêm khách hàng thành công! MaKH: {new_customer_id}")
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


@app.route('/add_Laptop', methods=['GET'])
def add_laptop_form():
    return render_template('themLapTop.html')


@app.route('/edit_Laptop/<int:maSP>', methods=['GET'])
def edit_laptop_form(maSP):
    return render_template('suaLapTop.html')


@app.route('/api/laptop/<int:maSP>', methods=['GET'])
def get_laptop(maSP):
    """Lấy thông tin chi tiết của một laptop theo MaSP"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM Laptop WHERE MaSP = ?", (maSP,))
        columns = [column[0] for column in cursor.description]
        row = cursor.fetchone()
        conn.close()

        if row:
            laptop = dict(zip(columns, row))
            return jsonify({
                "status": "success",
                "data": laptop
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Không tìm thấy laptop"
            }), 404

    except Exception as e:
        print("Lỗi:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/add_laptop', methods=['POST'])
def add_laptop():
    """Thêm laptop mới vào database"""
    data = request.get_json()

    TenSP = data.get('TenSP')
    Hang = data.get('Hang')
    GiaBan = data.get('GiaBan')
    CauHinh = data.get('CauHinh')
    Kho = data.get('Kho', 0)
    MaNCC = data.get('MaNCC')
    NgayNhap = data.get('NgayNhap')

    if not TenSP or not Hang or GiaBan is None:
        return jsonify({
            "status": "error",
            "message": "Thiếu thông tin bắt buộc (Tên SP, Hãng, Giá Bán)"
        }), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO Laptop (TenSP, Hang, GiaBan, CauHinh, Kho, MaNCC, NgayNhap)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """

        cursor.execute(insert_query, (TenSP, Hang, GiaBan, CauHinh, Kho, MaNCC,NgayNhap))
        conn.commit()


        cursor.execute("SELECT SCOPE_IDENTITY() AS MaSP")
        result = cursor.fetchone()


        conn.close()

        print(f"✓ Thêm laptop thành công!")
        return jsonify({
            "status": "success",
            "TenSP": TenSP,
            "NgayNhap": NgayNhap
        }), 201

    except Exception as e:
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        print("Lỗi:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/update_laptop/<int:maSP>', methods=['PUT'])
def update_laptop(maSP):
    """Cập nhật thông tin laptop"""
    data = request.get_json()

    TenSP = data.get('TenSP')
    Hang = data.get('Hang')
    GiaBan = data.get('GiaBan')
    CauHinh = data.get('CauHinh')
    Kho = data.get('Kho')
    MaNCC = data.get('MaNCC')
    NgayNhap = data.get('NgayNhap')

    if not TenSP or not Hang or GiaBan is None:
        return jsonify({
            "status": "error",
            "message": "Thiếu thông tin bắt buộc (Tên SP, Hãng, Giá Bán)"
        }), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()


        cursor.execute("SELECT MaSP FROM Laptop WHERE MaSP = ?", (maSP,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({
                "status": "error",
                "message": "Không tìm thấy laptop"
            }), 404

        update_query = """
            UPDATE Laptop
            SET TenSP = ?, Hang = ?, GiaBan = ?, CauHinh = ?, Kho = ?, MaNCC = ?, NgayNhap = ?
            WHERE MaSP = ?
        """

        cursor.execute(update_query, (TenSP, Hang, GiaBan, CauHinh, Kho, MaNCC, NgayNhap, maSP))
        conn.commit()
        conn.close()

        print(f"✓ Cập nhật laptop thành công!")
        return jsonify({
            "status": "success",
            "message": "Cập nhật thành công"
        }), 200

    except Exception as e:
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        print("Lỗi:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/delete_laptop/<int:maSP>', methods=['DELETE'])
def delete_laptop(maSP):
    """Xóa laptop khỏi database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Kiểm tra laptop có tồn tại không
        cursor.execute("SELECT TenSP FROM Laptop WHERE MaSP = ?", (maSP,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return jsonify({
                "status": "error",
                "message": "Không tìm thấy laptop"
            }), 404

        ten_sp = result[0]

        # Xóa laptop
        cursor.execute("DELETE FROM Laptop WHERE MaSP = ?", (maSP,))
        conn.commit()
        conn.close()

        print(f"✓ Xóa laptop thành công! MaSP: {maSP}, Tên: {ten_sp}")
        return jsonify({
            "status": "success",
            "message": f"Đã xóa laptop {ten_sp}"
        }), 200

    except pyodbc.IntegrityError as e:
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        return jsonify({
            "status": "error",
            "message": "Không thể xóa laptop vì đã có đơn hàng liên quan"
        }), 400
    except Exception as e:
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        print("Lỗi:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'True') == 'True'
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', '5000'))

    app.run(debug=debug_mode, host=host, port=port)
