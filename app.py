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

    # Validation cơ bản
    if not MaKH or not MaNV or not NgayGiao or not TrangThaiXuLy or not ChiTiet:
        return jsonify({"status": "error", "message": "Thiếu thông tin bắt buộc"}), 400

    # Validate MaKH và MaNV phải là số
    try:
        MaKH = int(MaKH)
        MaNV = int(MaNV)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Mã khách hàng và mã nhân viên phải là số"}), 400

    # Validate NgayGiao không được là quá khứ
    try:
        ngay_giao_date = datetime.datetime.strptime(NgayGiao, '%Y-%m-%d').date()
        hom_nay = datetime.datetime.now().date()
        if ngay_giao_date < hom_nay:
            return jsonify({"status": "error", "message": "Ngày giao hàng không được là quá khứ"}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Định dạng ngày giao không hợp lệ (yêu cầu: YYYY-MM-DD)"}), 400

    # Validate trạng thái
    valid_statuses = ['Chưa xử lý', 'Đang giao', 'Hoàn tất']
    if TrangThaiXuLy not in valid_statuses:
        return jsonify({"status": "error", "message": f"Trạng thái không hợp lệ. Phải là: {', '.join(valid_statuses)}"}), 400

    # Validate ChiTiet không rỗng
    if len(ChiTiet) == 0:
        return jsonify({"status": "error", "message": "Đơn hàng phải có ít nhất 1 sản phẩm"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Kiểm tra MaKH tồn tại
        cursor.execute("SELECT MaKH, TrangThai FROM KhachHang WHERE MaKH = ?", (MaKH,))
        kh_result = cursor.fetchone()
        if not kh_result:
            conn.close()
            return jsonify({"status": "error", "message": f"Không tìm thấy khách hàng với mã {MaKH}"}), 400
        if kh_result[1] != 'Active':
            conn.close()
            return jsonify({"status": "error", "message": "Khách hàng không ở trạng thái hoạt động"}), 400

        # Kiểm tra MaNV tồn tại
        cursor.execute("SELECT MaNV FROM NhanVien WHERE MaNV = ?", (MaNV,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"status": "error", "message": f"Không tìm thấy nhân viên với mã {MaNV}"}), 400

        # Validate từng sản phẩm trong chi tiết đơn hàng
        for idx, item in enumerate(ChiTiet, 1):
            maSP = item.get('MaSP')
            soLuongDat = item.get('SoLuong')
            giaBan = item.get('GiaBan')

            # Validate dữ liệu chi tiết
            if not maSP or not soLuongDat or giaBan is None:
                conn.close()
                return jsonify({"status": "error", "message": f"Sản phẩm thứ {idx} thiếu thông tin (MaSP, SoLuong, GiaBan)"}), 400

            try:
                maSP = int(maSP)
                soLuongDat = int(soLuongDat)
                giaBan = float(giaBan)
            except (ValueError, TypeError):
                conn.close()
                return jsonify({"status": "error", "message": f"Sản phẩm thứ {idx} có dữ liệu không hợp lệ"}), 400

            if soLuongDat <= 0:
                conn.close()
                return jsonify({"status": "error", "message": f"Sản phẩm thứ {idx}: Số lượng phải lớn hơn 0"}), 400

            if giaBan <= 0:
                conn.close()
                return jsonify({"status": "error", "message": f"Sản phẩm thứ {idx}: Giá bán phải lớn hơn 0"}), 400
            
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

    HoTen = data.get('HoTen', '').strip()
    GioiTinh = data.get('GioiTinh')
    NgaySinh = data.get('NgaySinh')
    SDT = data.get('SDT', '').strip()
    DiaChi = data.get('DiaChi', '').strip() if data.get('DiaChi') else None
    TrangThai = data.get('TrangThai', 'Active')

    # Validation họ tên
    if not HoTen:
        return jsonify({"status": "error", "message": "Họ tên là bắt buộc"}), 400

    if len(HoTen) < 2:
        return jsonify({"status": "error", "message": "Họ tên phải có ít nhất 2 ký tự"}), 400

    if len(HoTen) > 100:
        return jsonify({"status": "error", "message": "Họ tên không được quá 100 ký tự"}), 400

    # Validate số điện thoại
    if not SDT:
        return jsonify({"status": "error", "message": "Số điện thoại là bắt buộc"}), 400

    # Kiểm tra định dạng SDT (10-11 số)
    if not SDT.isdigit():
        return jsonify({"status": "error", "message": "Số điện thoại chỉ được chứa chữ số"}), 400

    if len(SDT) < 10 or len(SDT) > 11:
        return jsonify({"status": "error", "message": "Số điện thoại phải có 10-11 chữ số"}), 400

    # Validate giới tính
    valid_genders = ['Nam', 'Nu', 'Khac', None]
    if GioiTinh not in valid_genders:
        return jsonify({"status": "error", "message": "Giới tính không hợp lệ"}), 400

    # Validate ngày sinh (không được tương lai)
    if NgaySinh:
        try:
            ngay_sinh_date = datetime.datetime.strptime(NgaySinh, '%Y-%m-%d').date()
            hom_nay = datetime.datetime.now().date()
            if ngay_sinh_date > hom_nay:
                return jsonify({"status": "error", "message": "Ngày sinh không được là tương lai"}), 400

            # Kiểm tra tuổi hợp lý (ít nhất 13 tuổi)
            tuoi = (hom_nay - ngay_sinh_date).days / 365.25
            if tuoi < 13:
                return jsonify({"status": "error", "message": "Khách hàng phải ít nhất 13 tuổi"}), 400

            if tuoi > 150:
                return jsonify({"status": "error", "message": "Ngày sinh không hợp lệ"}), 400
        except ValueError:
            return jsonify({"status": "error", "message": "Định dạng ngày sinh không hợp lệ (yêu cầu: YYYY-MM-DD)"}), 400

    # Validate trạng thái
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

@app.route('/search_KhachHang', methods=['GET'])
def search_customer_page():
    return render_template('timKiemKhachHang.html')


@app.route('/api/search_KhachHang', methods=['GET'])
def search_KhachHang():
    search_term = request.args.get('q', '').strip()

    if not search_term:
        return jsonify({"status": "error", "message": "Thiếu từ khóa tìm kiếm"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        search_pattern = f'%{search_term}%'

        query = """
            SELECT
                kh.MaKH,
                kh.HoTen,
                kh.GioiTinh,
                kh.NgaySinh,
                kh.SDT,
                kh.DiaChi,
                kh.TrangThai
            FROM KhachHang kh
            WHERE kh.SDT LIKE ?
               OR kh.HoTen LIKE ?
               OR kh.HoTen COLLATE Latin1_General_CI_AI LIKE ?
            ORDER BY kh.TrangThai DESC, kh.HoTen ASC
        """

        cursor.execute(query, (search_pattern, search_pattern, search_pattern))
        rows = cursor.fetchall()
        conn.close()

        customers = []
        for row in rows:
            customers.append({
                'MaKH': row[0],
                'HoTen': row[1],
                'GioiTinh': row[2],
                'NgaySinh': row[3].isoformat() if row[3] else None,
                'SDT': row[4],
                'DiaChi': row[5],
                'TrangThai': row[6]
            })

        return jsonify({
            "status": "success",
            "data": customers,
            "count": len(customers)
        }), 200

    except Exception as e:
        print("Lỗi tìm kiếm:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/thong_ke_doanh_thu', methods=['GET'])
def thong_ke_doanh_thu_page():
    return render_template('thongKeDoanhThu.html')


@app.route('/api/thong_ke_doanh_thu', methods=['GET'])
def thong_ke_doanh_thu():
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    if not from_date or not to_date:
        return jsonify({
            "status": "error",
            "message": "Thiếu thông tin ngày bắt đầu hoặc ngày kết thúc"
        }), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query đơn hàng
        query_orders = """
            SELECT
                dh.MaDH,
                dh.ThoiGianTao,
                kh.HoTen as TenKhachHang,
                nv.HoTen as TenNhanVien,
                dh.TrangThaiXuLy,
                dh.TongTien
            FROM DonHang dh
            INNER JOIN KhachHang kh ON dh.MaKH = kh.MaKH
            INNER JOIN NhanVien nv ON dh.MaNV = nv.MaNV
            WHERE CAST(dh.ThoiGianTao AS DATE) >= ?
              AND CAST(dh.ThoiGianTao AS DATE) <= ?
            ORDER BY dh.ThoiGianTao DESC
        """

        cursor.execute(query_orders, (from_date, to_date))
        rows = cursor.fetchall()

        orders = []
        total_revenue = 0
        completed_revenue = 0

        for row in rows:
            order = {
                'MaDH': row[0],
                'ThoiGianTao': row[1].isoformat() if row[1] else None,
                'TenKhachHang': row[2],
                'TenNhanVien': row[3],
                'TrangThaiXuLy': row[4],
                'TongTien': float(row[5]) if row[5] else 0
            }
            orders.append(order)
            total_revenue += order['TongTien']
            if order['TrangThaiXuLy'] == 'Hoàn tất':
                completed_revenue += order['TongTien']

        # Query doanh số theo nhân viên
        query_employee_stats = """
            SELECT
                nv.HoTen as TenNhanVien,
                COUNT(dh.MaDH) as SoDonHang,
                SUM(dh.TongTien) as TongDoanhThu
            FROM DonHang dh
            INNER JOIN NhanVien nv ON dh.MaNV = nv.MaNV
            WHERE CAST(dh.ThoiGianTao AS DATE) >= ?
              AND CAST(dh.ThoiGianTao AS DATE) <= ?
            GROUP BY nv.MaNV, nv.HoTen
            ORDER BY TongDoanhThu DESC
        """

        cursor.execute(query_employee_stats, (from_date, to_date))
        employee_rows = cursor.fetchall()

        employee_stats = []
        for row in employee_rows:
            employee_stats.append({
                'TenNhanVien': row[0],
                'SoDonHang': row[1],
                'TongDoanhThu': float(row[2]) if row[2] else 0
            })

        # Query doanh số theo sản phẩm
        query_product_stats = """
            SELECT
                l.TenSP,
                SUM(ct.SoLuong) as SoLuongBan,
                SUM(ct.SoLuong * ct.GiaBan) as DoanhThu
            FROM ChiTietDonHang ct
            INNER JOIN Laptop l ON ct.MaSP = l.MaSP
            INNER JOIN DonHang dh ON ct.MaDH = dh.MaDH
            WHERE CAST(dh.ThoiGianTao AS DATE) >= ?
              AND CAST(dh.ThoiGianTao AS DATE) <= ?
            GROUP BY l.MaSP, l.TenSP
            ORDER BY SoLuongBan DESC
        """

        cursor.execute(query_product_stats, (from_date, to_date))
        product_rows = cursor.fetchall()

        product_stats = []
        for row in product_rows:
            product_stats.append({
                'TenSP': row[0],
                'SoLuongBan': row[1],
                'DoanhThu': float(row[2]) if row[2] else 0
            })

        # Top 5 sản phẩm bán chạy
        top_products = product_stats[:5]

        conn.close()

        # Tính toán thống kê
        total_orders = len(orders)
        avg_revenue = total_revenue / total_orders if total_orders > 0 else 0

        return jsonify({
            "status": "success",
            "summary": {
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "completed_revenue": completed_revenue,
                "avg_revenue": avg_revenue
            },
            "orders": orders,
            "employee_stats": employee_stats,
            "product_stats": product_stats,
            "top_products": top_products
        }), 200

    except Exception as e:
        print("Lỗi thống kê:", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


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

    TenSP = data.get('TenSP', '').strip()
    Hang = data.get('Hang', '').strip()
    GiaBan = data.get('GiaBan')
    CauHinh = data.get('CauHinh', '').strip() if data.get('CauHinh') else None
    Kho = data.get('Kho', 0)
    MaNCC = data.get('MaNCC')
    NgayNhap = data.get('NgayNhap')
    TrangThai = data.get('TrangThai', 'Active')

    # Validation cơ bản
    if not TenSP or not Hang or GiaBan is None:
        return jsonify({
            "status": "error",
            "message": "Thiếu thông tin bắt buộc (Tên SP, Hãng, Giá Bán)"
        }), 400

    # Validate độ dài tên sản phẩm
    if len(TenSP) < 3:
        return jsonify({
            "status": "error",
            "message": "Tên sản phẩm phải có ít nhất 3 ký tự"
        }), 400

    if len(TenSP) > 255:
        return jsonify({
            "status": "error",
            "message": "Tên sản phẩm không được quá 255 ký tự"
        }), 400

    # Validate hãng
    if len(Hang) < 2:
        return jsonify({
            "status": "error",
            "message": "Tên hãng phải có ít nhất 2 ký tự"
        }), 400

    # Validate giá bán
    try:
        GiaBan = float(GiaBan)
        if GiaBan <= 0:
            return jsonify({
                "status": "error",
                "message": "Giá bán phải lớn hơn 0"
            }), 400
        if GiaBan > 1000000000:  # 1 tỷ
            return jsonify({
                "status": "error",
                "message": "Giá bán không hợp lệ (quá lớn)"
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            "status": "error",
            "message": "Giá bán phải là số"
        }), 400

    # Validate kho
    try:
        Kho = int(Kho)
        if Kho < 0:
            return jsonify({
                "status": "error",
                "message": "Số lượng kho không được âm"
            }), 400
        if Kho > 100000:
            return jsonify({
                "status": "error",
                "message": "Số lượng kho không hợp lệ (quá lớn)"
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            "status": "error",
            "message": "Số lượng kho phải là số nguyên"
        }), 400

    # Validate ngày nhập (không được tương lai)
    if NgayNhap:
        try:
            ngay_nhap_date = datetime.datetime.strptime(NgayNhap, '%Y-%m-%d').date()
            hom_nay = datetime.datetime.now().date()
            if ngay_nhap_date > hom_nay:
                return jsonify({
                    "status": "error",
                    "message": "Ngày nhập không được là tương lai"
                }), 400
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Định dạng ngày nhập không hợp lệ (yêu cầu: YYYY-MM-DD)"
            }), 400

    # Validate trạng thái
    valid_statuses = ['Active', 'Ngừng kinh doanh']
    if TrangThai not in valid_statuses:
        return jsonify({
            "status": "error",
            "message": f"Trạng thái không hợp lệ. Phải là: {', '.join(valid_statuses)}"
        }), 400

    # Validate MaNCC nếu có
    if MaNCC:
        try:
            MaNCC = int(MaNCC)
            conn_temp = get_db_connection()
            cursor_temp = conn_temp.cursor()
            cursor_temp.execute("SELECT MaNCC FROM NhaCungCap WHERE MaNCC = ?", (MaNCC,))
            if not cursor_temp.fetchone():
                conn_temp.close()
                return jsonify({
                    "status": "error",
                    "message": f"Không tìm thấy nhà cung cấp với mã {MaNCC}"
                }), 400
            conn_temp.close()
        except (ValueError, TypeError):
            return jsonify({
                "status": "error",
                "message": "Mã nhà cung cấp phải là số"
            }), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO Laptop (TenSP, Hang, GiaBan, CauHinh, Kho, MaNCC, NgayNhap,TrangThai)
            VALUES (?, ?, ?, ?, ?, ?, ?,?);
        """

        cursor.execute(insert_query, (TenSP, Hang, GiaBan, CauHinh, Kho, MaNCC,NgayNhap,TrangThai))
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

    TenSP = data.get('TenSP', '').strip()
    Hang = data.get('Hang', '').strip()
    GiaBan = data.get('GiaBan')
    CauHinh = data.get('CauHinh', '').strip() if data.get('CauHinh') else None
    Kho = data.get('Kho')
    MaNCC = data.get('MaNCC')
    NgayNhap = data.get('NgayNhap')
    TrangThai = data.get('TrangThai', 'Active')

    # Validation cơ bản
    if not TenSP or not Hang or GiaBan is None:
        return jsonify({
            "status": "error",
            "message": "Thiếu thông tin bắt buộc (Tên SP, Hãng, Giá Bán)"
        }), 400

    # Validate độ dài tên sản phẩm
    if len(TenSP) < 3:
        return jsonify({
            "status": "error",
            "message": "Tên sản phẩm phải có ít nhất 3 ký tự"
        }), 400

    if len(TenSP) > 255:
        return jsonify({
            "status": "error",
            "message": "Tên sản phẩm không được quá 255 ký tự"
        }), 400

    # Validate hãng
    if len(Hang) < 2:
        return jsonify({
            "status": "error",
            "message": "Tên hãng phải có ít nhất 2 ký tự"
        }), 400

    # Validate giá bán
    try:
        GiaBan = float(GiaBan)
        if GiaBan <= 0:
            return jsonify({
                "status": "error",
                "message": "Giá bán phải lớn hơn 0"
            }), 400
        if GiaBan > 1000000000:
            return jsonify({
                "status": "error",
                "message": "Giá bán không hợp lệ (quá lớn)"
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            "status": "error",
            "message": "Giá bán phải là số"
        }), 400

    # Validate kho
    try:
        Kho = int(Kho)
        if Kho < 0:
            return jsonify({
                "status": "error",
                "message": "Số lượng kho không được âm"
            }), 400
        if Kho > 100000:
            return jsonify({
                "status": "error",
                "message": "Số lượng kho không hợp lệ (quá lớn)"
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            "status": "error",
            "message": "Số lượng kho phải là số nguyên"
        }), 400

    # Validate ngày nhập
    if NgayNhap:
        try:
            ngay_nhap_date = datetime.datetime.strptime(NgayNhap, '%Y-%m-%d').date()
            hom_nay = datetime.datetime.now().date()
            if ngay_nhap_date > hom_nay:
                return jsonify({
                    "status": "error",
                    "message": "Ngày nhập không được là tương lai"
                }), 400
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Định dạng ngày nhập không hợp lệ (yêu cầu: YYYY-MM-DD)"
            }), 400

    # Validate trạng thái
    valid_statuses = ['Active', 'Ngừng kinh doanh']
    if TrangThai not in valid_statuses:
        return jsonify({
            "status": "error",
            "message": f"Trạng thái không hợp lệ. Phải là: {', '.join(valid_statuses)}"
        }), 400

    # Validate MaNCC nếu có
    if MaNCC:
        try:
            MaNCC = int(MaNCC)
            conn_temp = get_db_connection()
            cursor_temp = conn_temp.cursor()
            cursor_temp.execute("SELECT MaNCC FROM NhaCungCap WHERE MaNCC = ?", (MaNCC,))
            if not cursor_temp.fetchone():
                conn_temp.close()
                return jsonify({
                    "status": "error",
                    "message": f"Không tìm thấy nhà cung cấp với mã {MaNCC}"
                }), 400
            conn_temp.close()
        except (ValueError, TypeError):
            return jsonify({
                "status": "error",
                "message": "Mã nhà cung cấp phải là số"
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
            SET TenSP = ?, Hang = ?, GiaBan = ?, CauHinh = ?, Kho = ?, MaNCC = ?, NgayNhap = ?, TrangThai=?
            WHERE MaSP = ?
        """

        cursor.execute(update_query, (TenSP, Hang, GiaBan, CauHinh, Kho, MaNCC, NgayNhap, TrangThai, maSP))
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


@app.route('/xem_hoa_don/<int:order_id>')
def xem_hoa_don(order_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Lấy thông tin đơn hàng
        cursor.execute("""
            SELECT MaDH, MaKH, MaNV, NgayGiao, ThoiGianTao, TrangThaiXuLy, TongTien, GhiChu
            FROM DonHang WHERE MaDH = ?
        """, (order_id,))
        don_hang = cursor.fetchone()

        if not don_hang:
            conn.close()
            return "Không tìm thấy đơn hàng", 404

        # Lấy thông tin khách hàng
        cursor.execute("SELECT MaKH, HoTen, SDT, DiaChi FROM KhachHang WHERE MaKH = ?", (don_hang[1],))
        khach_hang = cursor.fetchone()

        # Lấy thông tin nhân viên
        cursor.execute("SELECT MaNV, HoTen, SDT FROM NhanVien WHERE MaNV = ?", (don_hang[2],))
        nhan_vien = cursor.fetchone()

        # Lấy chi tiết sản phẩm
        cursor.execute("""
            SELECT L.TenSP, CT.SoLuong, CT.GiaBan, (CT.SoLuong * CT.GiaBan) as ThanhTien
            FROM ChiTietDonHang CT
            JOIN Laptop L ON CT.MaSP = L.MaSP
            WHERE CT.MaDH = ?
        """, (order_id,))
        chi_tiet = cursor.fetchall()

        conn.close()

        # Format dữ liệu
        def format_tien(so):
            return "{:,.0f} ₫".format(float(so)).replace(',', '.')

        # Chuẩn bị danh sách sản phẩm
        danh_sach_sp = []
        tong_sl = 0
        for item in chi_tiet:
            tong_sl += int(item[1])
            danh_sach_sp.append({
                'ten': item[0],
                'soluong': int(item[1]),
                'gia': format_tien(item[2]),
                'thanhtien': format_tien(item[3])
            })

        # Chuẩn bị dữ liệu cho template
        data = {
            'ma_dh': don_hang[0],
            'ngay_giao': don_hang[3].strftime('%d/%m/%Y') if don_hang[3] else '',
            'ngay_tao': don_hang[4].strftime('%d/%m/%Y %H:%M') if don_hang[4] else '',
            'trang_thai': don_hang[5] or '',
            'ghi_chu': don_hang[7] or '',
            'kh_ma': khach_hang[0] if khach_hang else '',
            'kh_ten': khach_hang[1] if khach_hang else '',
            'kh_sdt': khach_hang[2] if khach_hang else '',
            'kh_diachi': khach_hang[3] if khach_hang else 'Chưa cập nhật',
            'nv_ma': nhan_vien[0] if nhan_vien else '',
            'nv_ten': nhan_vien[1] if nhan_vien else '',
            'nv_sdt': nhan_vien[2] if nhan_vien else '',
            'san_pham': danh_sach_sp,
            'tong_soluong': tong_sl,
            'tong_tien': format_tien(don_hang[6])
        }

        return render_template('xemHoaDon.html', **data)

    except Exception as e:
        return f"Lỗi: {str(e)}", 500


if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'True') == 'True'
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', '5000'))

    app.run(debug=debug_mode, host=host, port=port)
