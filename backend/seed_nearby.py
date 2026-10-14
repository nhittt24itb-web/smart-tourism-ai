from backend.database import SessionLocal
from backend import models

def seed_nearby_places():
    db = SessionLocal()
    try:
        # Danh sách các địa điểm quanh Đà Nẵng có tọa độ GPS chuẩn
        places = [
            {
                "name": "Skyview Coffee Rooftop & Lounge",
                "city": "Đà Nẵng",
                "category_name": "Cafe Rooftop",
                "latitude": 16.0612,
                "longitude": 108.2235,
                "opening_hours": "Mở cửa đến 23:00",
                "short_description": "Tầng 19, ngắm toàn cảnh Cầu Rồng phun lửa vào cuối tuần",
                "featured_image": "assets/images/nha trang.jpg",
                "rating": 4.8,
                "review_count": 320,
                "is_active": True
            },
            {
                "name": "Bảo Tàng Điêu Khắc Chăm Pa",
                "city": "Đà Nẵng",
                "category_name": "Di tích văn hóa",
                "latitude": 16.0598,
                "longitude": 108.2229,
                "opening_hours": "07:30 - 17:00",
                "short_description": "Di sản khảo cổ học đặc sắc nhất Đông Nam Á",
                "featured_image": "assets/images/anh2.jpg",
                "rating": 4.7,
                "review_count": 510,
                "is_active": True
            },
            {
                "name": "Phố Đi Bộ & Bờ Đông Cầu Rồng",
                "city": "Đà Nẵng",
                "category_name": "Điểm Check-in",
                "latitude": 16.0614,
                "longitude": 108.2285,
                "opening_hours": "Mở cả ngày",
                "short_description": "Không gian dạo mát, ẩm thực đường phố và cầu Tình Yêu",
                "featured_image": "assets/images/ba na hill, da nang.jpg",
                "rating": 4.9,
                "review_count": 890,
                "is_active": True
            },
            {
                "name": "Cầu Tình Yêu & Tượng Cá Chép Hóa Rồng",
                "city": "Đà Nẵng",
                "category_name": "Điểm Check-in",
                "latitude": 16.0625,
                "longitude": 108.2290,
                "opening_hours": "Mở cả ngày",
                "short_description": "Địa điểm check-in lãng mạn bên bờ sông Hàn",
                "featured_image": "assets/images/anh1.jpg",
                "rating": 4.6,
                "review_count": 420,
                "is_active": True
            }
        ]

        for p in places:
            existing = db.query(models.Destination).filter(models.Destination.name == p["name"]).first()
            if not existing:
                dest = models.Destination(**p)
                db.add(dest)
        
        db.commit()
        print(" Đã thêm thành công các địa điểm lân cận vào MySQL!")
    except Exception as e:
        print("Lỗi khi thêm dữ liệu:", e)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_nearby_places()