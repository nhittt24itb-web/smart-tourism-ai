import os
import re
import pandas as pd
from sqlalchemy import create_engine, text

# 1. Đường dẫn dataset và cấu hình MySQL
CSV_PATH = r"D:\Trí tuệ nhân tạo\smart-tourism-ai\dataset\raw\vietnam_tourism_34_tinh_thanh.csv"
DB_USER = "root"
DB_PASSWORD = ""  # <-- Đổi thành mật khẩu MySQL của bạn
DB_HOST = "localhost"
DB_PORT = "3306"
DB_NAME = "smart_tourism"

def slugify(text_val):
    if not isinstance(text_val, str) or not text_val:
        return "destination"
    text_val = text_val.lower().strip()
    text_val = re.sub(r'[^\w\s-]', '', text_val)
    return re.sub(r'[-\s]+', '-', text_val)

def main():
    if not os.path.exists(CSV_PATH):
        print(f"Lỗi: Không tìm thấy file tại {CSV_PATH}")
        return

    # Kết nối MySQL
    connection_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    engine = create_engine(connection_url)

    print(" Đang đọc dữ liệu từ file CSV...")
    df = pd.read_csv(CSV_PATH, encoding="utf-8")
    print(f" Đã đọc {len(df)} dòng dữ liệu.")

    # 1. Xử lý danh mục (categories) để đảm bảo ràng buộc khóa ngoại
    categories_raw = df['category'].dropna().unique()
    categories_map = {}

    with engine.begin() as conn:
        for idx, cat_name in enumerate(categories_raw, start=1):
            cat_slug = slugify(cat_name)
            # Thêm category vào database nếu chưa có
            conn.execute(text("""
                INSERT INTO categories (name, slug, description)
                VALUES (:name, :slug, :desc)
                ON DUPLICATE KEY UPDATE name = VALUES(name);
            """), {"name": cat_name, "slug": cat_slug, "desc": f"Danh mục {cat_name}"})
        
        # Lấy lại mapping ID từ database
        result = conn.execute(text("SELECT id, name FROM categories;")).fetchall()
        categories_map = {row[1]: row[0] for row in result}

    print(f" Đã đồng bộ {len(categories_map)} danh mục vào bảng categories.")

    # 2. Xử lý và chuẩn hóa dữ liệu bảng destinations
    dest_df = pd.DataFrame()
    dest_df['name'] = df['name'].fillna('Không có tên')
    dest_df['city'] = df['city'].fillna('Chưa xác định')
    dest_df['district'] = df['district'].fillna('')
    dest_df['description'] = df['description'].fillna('')
    dest_df['short_description'] = dest_df['description'].astype(str).str.slice(0, 200)

    # Tọa độ
    dest_df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce').fillna(0.0)
    dest_df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce').fillna(0.0)

    # Đánh giá & chi phí
    dest_df['rating'] = pd.to_numeric(df['rating'], errors='coerce').fillna(0.0)
    dest_df['review_count'] = pd.to_numeric(df['review_count'], errors='coerce').fillna(0).astype(int)
    dest_df['estimated_cost'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0)
    dest_df['price_level'] = dest_df['estimated_cost'].apply(
        lambda p: 'Free' if p == 0 else ('Low' if p < 100000 else ('Medium' if p < 500000 else 'High'))
    )

    # Đặc tính địa điểm (indoor / outdoor)
    dest_df['is_indoor'] = df['indoor'].astype(bool).fillna(False)
    dest_df['is_outdoor'] = df['outdoor'].astype(bool).fillna(True)

    # Ảnh đại diện
    dest_df['featured_image'] = df['featured_image'].fillna('')

    # Ánh xạ category_id khóa ngoại
    default_cat_id = next(iter(categories_map.values())) if categories_map else 1
    dest_df['category_id'] = df['category'].map(categories_map).fillna(default_cat_id).astype(int)

    # Các trường bắt buộc theo schema
    dest_df['slug'] = dest_df['name'].apply(slugify) + "-" + df.index.astype(str)
    dest_df['is_active'] = True

    # 3. Ghi vào bảng destinations
    print(" Đang nạp dữ liệu vào bảng 'destinations'...")
    dest_df.to_sql(name='destinations', con=engine, if_exists='append', index=False, chunksize=500)
    print(" Import thành công toàn bộ 658 địa điểm vào MySQL!")

if __name__ == "__main__":
    main()