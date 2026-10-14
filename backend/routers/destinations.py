import math
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from backend.database import get_db
from backend import models, schemas

router = APIRouter(prefix="/api/destinations", tags=["Destinations"])

# Bảng map tên danh mục dự phòng theo category_id
CATEGORY_NAME_MAP = {
    1: "Thiên nhiên & Sinh thái",
    2: "Di tích & Văn hóa",
    3: "Biển đảo & Nghỉ dưỡng",
    4: "Ẩm thực & Chợ đêm",
    5: "Vui chơi & Check-in"
}

def resolve_category_name(dest):
    if hasattr(dest, 'category') and dest.category:
        return dest.category
    cat_id = getattr(dest, 'category_id', 2)
    return CATEGORY_NAME_MAP.get(cat_id, "Du lịch & Trải nghiệm")


# 1. Pydantic Schema nhận dữ liệu đánh giá
class ReviewCreate(BaseModel):
    destination_id: int
    user_id: Optional[int] = None
    rating: int = Field(..., ge=1, le=5, description="Số sao từ 1 đến 5")
    comment: Optional[str] = ""


# 2. Endpoint: Gửi đánh giá mới & tự động tính lại điểm sao trung bình thật
@router.post("/review", summary="Gửi đánh giá thực tế từ người dùng")
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)):
    destination = db.query(models.Destination).filter(models.Destination.id == payload.destination_id).first()
    if not destination:
        raise HTTPException(status_code=404, detail="Không tìm thấy địa điểm này")

    uid = payload.user_id if payload.user_id else 1

    new_rev = models.Review(
        destination_id=payload.destination_id,
        user_id=uid,
        rating=payload.rating,
        comment=payload.comment.strip() if payload.comment else "",
        sentiment_score=0.0,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(new_rev)
    db.flush()

    stats = db.query(
        func.avg(models.Review.rating).label("avg_rating"),
        func.count(models.Review.id).label("total_reviews")
    ).filter(models.Review.destination_id == payload.destination_id).first()

    avg_score = round(float(stats.avg_rating), 1) if stats.avg_rating else float(payload.rating)
    total_count = int(stats.total_reviews) if stats.total_reviews else 1

    destination.rating = avg_score
    destination.review_count = total_count

    db.commit()

    return {
        "status": "success",
        "new_rating": avg_score,
        "new_review_count": total_count,
        "message": f"Đã ghi nhận đánh giá {payload.rating} sao thành công!"
    }


# 3. Endpoint: Lấy danh sách đánh giá thực tế theo ID điểm đến
@router.get("/{dest_id}/reviews", summary="Lấy danh sách đánh giá của điểm đến")
def get_reviews_for_destination(dest_id: int, db: Session = Depends(get_db)):
    reviews = db.query(models.Review)\
                .filter(models.Review.destination_id == dest_id)\
                .order_by(models.Review.id.desc())\
                .limit(20)\
                .all()

    result = []
    for r in reviews:
        name = "Khách du lịch"
        if hasattr(r, 'user') and r.user:
            name = getattr(r.user, 'full_name', None) or getattr(r.user, 'username', None) or getattr(r.user, 'name', 'Khách du lịch')
        
        result.append({
            "id": r.id,
            "user_name": name,
            "rating": r.rating,
            "comment": r.comment or "Đánh giá không kèm nhận xét.",
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M") if r.created_at else ""
        })

    return result


# 4. API BỔ SUNG: Điểm đến Nổi bật (Featured) - Frontend index.html đang gọi endpoint này!
@router.get("/featured", summary="Lấy danh sách điểm đến nổi bật")
def get_featured_destinations(limit: int = 8, db: Session = Depends(get_db)):
    query = db.query(models.Destination).filter(models.Destination.is_active == 1)
    
    # Sắp xếp ưu tiên điểm có lượt đánh giá và rating cao
    items = query.order_by(models.Destination.rating.desc(), models.Destination.review_count.desc()).limit(limit).all()

    results = []
    for d in items:
        results.append({
            "id": d.id,
            "name": d.name,
            "city": d.city,
            "district": getattr(d, 'district', None) or "Trung tâm",
            "category": resolve_category_name(d),
            "rating": float(d.rating or 4.8),
            "review_count": getattr(d, 'review_count', 120) or 120,
            "estimated_cost": getattr(d, 'estimated_cost', 0) or 0,
            "price": "Miễn phí" if not d.estimated_cost else f"{int(d.estimated_cost):,} VNĐ".replace(",", "."),
            "is_indoor": bool(getattr(d, 'is_indoor', False)),
            "is_outdoor": bool(getattr(d, 'is_outdoor', True)),
            "featured_image": d.featured_image or "assets/images/anh1.jpg",
            "short_description": d.short_description or (d.description[:120] + "..." if d.description else ""),
            "description": d.description or d.short_description or "",
            "latitude": float(d.latitude or 16.0544),
            "longitude": float(d.longitude or 108.2022)
        })
    return results


# 5. API Lấy danh sách điểm đến phổ biến nhất (Popular)
@router.get("/popular", summary="Lấy danh sách thịnh hành tuần này")
def get_popular(limit: int = 6, db: Session = Depends(get_db)):
    items = db.query(models.Destination)\
              .filter(models.Destination.is_active == 1)\
              .order_by(models.Destination.review_count.desc())\
              .limit(limit).all()

    results = []
    for d in items:
        results.append({
            "id": d.id,
            "name": d.name,
            "city": d.city,
            "district": getattr(d, 'district', None) or "Trung tâm",
            "category": resolve_category_name(d),
            "rating": float(d.rating or 4.8),
            "review_count": getattr(d, 'review_count', 120) or 120,
            "estimated_cost": getattr(d, 'estimated_cost', 0) or 0,
            "price": "Miễn phí" if not d.estimated_cost else f"{int(d.estimated_cost):,} VNĐ".replace(",", "."),
            "is_indoor": bool(getattr(d, 'is_indoor', False)),
            "is_outdoor": bool(getattr(d, 'is_outdoor', True)),
            "featured_image": d.featured_image or "assets/images/anh1.jpg",
            "short_description": d.short_description or (d.description[:120] + "..." if d.description else ""),
            "description": d.description or d.short_description or "",
            "latitude": float(d.latitude or 16.0544),
            "longitude": float(d.longitude or 108.2022)
        })
    return results


# Hàm tính khoảng cách địa lý theo tọa độ mặt cầu Haversine (km)
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# 6. API Lấy danh sách địa điểm xung quanh vị trí bản đồ (Nearby)
@router.get("/nearby", summary="Lấy danh sách địa điểm gần tọa độ GPS")
def get_nearby_destinations(
    lat: float = Query(16.0544),
    lon: float = Query(108.2022),
    radius_km: float = Query(60.0),
    city: str = Query(None, description="Tên thành phố fallback"),
    limit: int = Query(4),
    db: Session = Depends(get_db)
):
    items = db.query(models.Destination).filter(
        models.Destination.is_active == 1,
        models.Destination.latitude.isnot(None),
        models.Destination.longitude.isnot(None)
    ).all()

    results = []
    for d in items:
        try:
            d_lat = float(d.latitude)
            d_lon = float(d.longitude)
            dist = haversine_km(lat, lon, d_lat, d_lon)
            
            is_matched = (dist <= radius_km)
            if not is_matched and city:
                if (d.city and city.lower() in d.city.lower()) or (d.district and city.lower() in d.district.lower()):
                    is_matched = True

            if is_matched:
                dist_str = f"{int(dist * 1000)} m" if dist < 1.0 else f"{round(dist, 1)} km"
                time_open = f"{d.opening_time or '08:00'} - {d.closing_time or '22:00'}"
                
                results.append({
                    "id": d.id,
                    "name": d.name,
                    "city": d.city,
                    "category": resolve_category_name(d),
                    "lat": d_lat,
                    "lon": d_lon,
                    "distance": dist,
                    "distance_label": dist_str,
                    "time_open": time_open,
                    "desc": d.short_description or d.description or "Địa điểm tham quan hấp dẫn",
                    "featured_image": d.featured_image
                })
        except Exception:
            continue

    results.sort(key=lambda x: x["distance"])
    return results[:limit]


# 7. API Lấy toàn bộ danh sách điểm đến cho trang Explore / Tìm kiếm
@router.get("", summary="Lấy toàn bộ danh sách điểm đến cho trang Explore / Tìm kiếm")
def get_all_destinations(
    search: Optional[str] = Query(None, description="Từ khóa tìm kiếm"),
    city: Optional[str] = Query(None, description="Lọc theo tỉnh thành"),
    limit: int = 500,
    db: Session = Depends(get_db)
):
    query = db.query(models.Destination).filter(models.Destination.is_active == 1)

    if search:
        search_kw = f"%{search.strip()}%"
        query = query.filter(
            or_(
                models.Destination.name.ilike(search_kw),
                models.Destination.city.ilike(search_kw),
                models.Destination.description.ilike(search_kw)
            )
        )

    if city and city != "all":
        query = query.filter(models.Destination.city.ilike(f"%{city.strip()}%"))

    results = query.order_by(models.Destination.id.asc()).limit(limit).all()

    dest_list = []
    for d in results:
        dest_list.append({
            "id": d.id,
            "name": d.name,
            "city": d.city,
            "district": getattr(d, 'district', None) or "Trung tâm",
            "category": resolve_category_name(d),
            "rating": float(d.rating or 4.8),
            "review_count": getattr(d, 'review_count', 120) or 120,
            "estimated_cost": getattr(d, 'estimated_cost', 0) or 0,
            "price": "Miễn phí" if not d.estimated_cost else f"{int(d.estimated_cost):,} VNĐ".replace(",", "."),
            "is_indoor": bool(getattr(d, 'is_indoor', False)),
            "is_outdoor": bool(getattr(d, 'is_outdoor', True)),
            "featured_image": d.featured_image or "assets/images/anh1.jpg",
            "short_description": getattr(d, 'short_description', None) or (d.description[:120] + "..." if d.description else ""),
            "description": d.description or getattr(d, 'short_description', ""),
            "latitude": float(getattr(d, 'latitude', 16.0544) or 16.0544),
            "longitude": float(getattr(d, 'longitude', 108.2022) or 108.2022)
        })

    return dest_list