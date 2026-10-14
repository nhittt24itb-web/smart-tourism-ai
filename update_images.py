import re
import pandas as pd
import pymysql

# 1. Cấu hình file CSV và MySQL
CSV_PATH = r"D:\smarttourism\dataset\raw\vietnam_tourism_34_tinh_thanh.csv"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "smart_tourism",
    "charset": "utf8mb4"
}

# 2. Hàm chuẩn hóa giá vé thành số tiền thực tế (VNĐ)
def parse_price_to_number(raw_val):
    if pd.isna(raw_val):
        return 0.0
    val_str = str(raw_val).strip().lower()
    
    if val_str in ['miễn phí', 'free', '0', '0k', 'low']:
        return 0.0
    if val_str == 'medium':
        return 500000.0
    if val_str == 'high':
        return 1500000.0
    
    # Khớp dạng: 1tr200k, 1tr099k, 1tr2
    m_tryk = re.match(r'^(\d+)\s*tr\s*(\d+)\s*k?$', val_str)
    if m_tryk:
        tr = int(m_tryk.group(1)) * 1_000_000
        k_str = m_tryk.group(2)
        # Nếu k_str dạng 2 (tức 1tr2) -> 200,000; nếu 200 -> 200,000
        if len(k_str) == 1:
            k = int(k_str) * 100_000
        elif len(k_str) == 2:
            k = int(k_str) * 10_000
        else:
            k = int(k_str) * 1_000
        return float(tr + k)
    
    # Khớp dạng: 2tr, 3tr
    m_tr = re.match(r'^(\d+)\s*tr$', val_str)
    if m_tr:
        return float(int(m_tr.group(1)) * 1_000_000)
    
    # Khớp dạng: 800k, 587k
    m_k = re.match(r'^(\d+)\s*k$', val_str)
    if m_k:
        return float(int(m_k.group(1)) * 1_000)
    
    # Số nguyên thuần
    nums = re.findall(r'\d+', val_str)
    if nums:
        val = int("".join(nums))
        return float(val * 1000 if val < 10000 else val)
    return 0.0

# 3. Hàm chuẩn hóa tọa độ (xử lý dải tọa độ và độ phút giây)
def clean_coordinate(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    try:
        return float(val_str)
    except ValueError:
        pass
    
    # Xử lý độ phút giây (DMS): ví dụ 9°52'45"
    dms_match = re.search(r'(\d+)°\s*(\d+)\'\s*(\d+)"?', val_str)
    if dms_match:
        d, m, s = map(float, dms_match.groups())
        return round(d + m / 60.0 + s / 3600.0, 5)
        
    # Xử lý dải khoảng cách: ví dụ 16.1208-16.1222 hoặc 9.8792 - 10.3305
    floats = [float(x) for x in re.findall(r'(\d+(?:\.\d+)?)', val_str)]
    if len(floats) >= 2:
        return round(sum(floats[:2]) / 2.0, 5)
    elif len(floats) == 1:
        return floats[0]
    return None

print(f"📂 Đang mở file CSV: {CSV_PATH}")

try:
    df = pd.read_csv(CSV_PATH, encoding="utf-8")
except UnicodeDecodeError:
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
except Exception as e:
    print(f"❌ Không thể đọc file CSV: {e}")
    exit()

if "id" not in df.columns:
    print("❌ Lỗi: File CSV bắt buộc phải có cột 'id'!")
    exit()

print(f"📊 Tìm thấy {len(df)} dòng dữ liệu trong CSV.")

try:
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Lấy danh sách các cột thực tế của bảng destinations trong MySQL
    cursor.execute("""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'destinations'
    """, (DB_CONFIG["database"],))
    
    db_columns = {row[0] for row in cursor.fetchall()}
    print(f"📋 Các cột trong MySQL destinations: {list(db_columns)}")

    # Các cột cần cập nhật tự động
    excluded_columns = {"id", "created_at", "updated_at"}
    matched_columns = [col for col in df.columns if col in db_columns and col not in excluded_columns]

    # Kiểm tra xem MySQL có cột estimated_cost không
    has_estimated_cost = "estimated_cost" in db_columns
    has_price = "price" in db_columns

    update_cols = list(matched_columns)
    if has_estimated_cost and "estimated_cost" not in update_cols:
        update_cols.append("estimated_cost")
    if has_price and "price" not in update_cols:
        update_cols.append("price")

    print(f"\n🔄 Danh sách các cột sẽ cập nhật vào MySQL: {update_cols}")

    # Sinh câu lệnh SQL UPDATE
    set_clause = ", ".join([f"`{col}` = %s" for col in update_cols])
    sql_update = f"UPDATE `destinations` SET {set_clause} WHERE `id` = %s"

    updated_count = 0
    total_rows = len(df)

    for idx, row in df.iterrows():
        dest_id = row.get("id")
        if pd.isna(dest_id):
            continue

        # Tính toán giá vé chuẩn
        raw_price_val = row.get("price") if "price" in df.columns else None
        cost_num = parse_price_to_number(raw_price_val)
        price_text = f"{int(cost_num):,} VNĐ".replace(",", ".") if cost_num > 0 else "Miễn phí"

        values = []
        for col in update_cols:
            if col == "estimated_cost":
                values.append(cost_num)
            elif col == "price":
                # Nếu MySQL dùng price dạng chuỗi định dạng đẹp
                values.append(price_text)
            elif col in ["latitude", "lat"]:
                values.append(clean_coordinate(row.get(col)))
            elif col in ["longitude", "lon", "lng"]:
                values.append(clean_coordinate(row.get(col)))
            elif col in ["indoor", "outdoor", "is_indoor", "is_outdoor"]:
                val = row.get(col)
                values.append(int(val) if pd.notna(val) else 0)
            elif col in ["rating"]:
                val = row.get(col)
                values.append(float(val) if pd.notna(val) else 4.5)
            elif col in ["review_count"]:
                val = row.get(col)
                values.append(int(val) if pd.notna(val) else 120)
            else:
                val = row.get(col)
                if pd.isna(val):
                    values.append(None)
                else:
                    values.append(str(val).strip())

        # Thêm dest_id cho mệnh đề WHERE id = %s
        values.append(int(dest_id))

        cursor.execute(sql_update, tuple(values))
        if cursor.rowcount > 0:
            updated_count += 1

        if (idx + 1) % 100 == 0 or (idx + 1) == total_rows:
            print(f"⏳ Tiến độ: {idx + 1}/{total_rows} dòng...")

    conn.commit()
    print(f"\n🎉 HOÀN TẤT! Đã đồng bộ và cập nhật thành công {updated_count}/{total_rows} bản ghi vào MySQL!")

except Exception as e:
    if "conn" in locals():
        conn.rollback()
    print(f"\n❌ Lỗi khi thao tác MySQL: {e}")
finally:
    if "cursor" in locals():
        cursor.close()
    if "conn" in locals():
        conn.close()