from pydantic import BaseModel
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend.database import get_db
from backend import models
from backend.services.itinerary_optimizer import haversine_distance

router = APIRouter(prefix="/api/trips", tags=["Trip Planner"])

class ItineraryFilterRequest(BaseModel):
    city: str = "Đà Nẵng"
    days: int = 3
    pace: str = "relax"          # "relax" hoặc "active"
    transport: str = "taxi"
    interests: List[str] = ["Thiên nhiên", "Văn hóa", "Ẩm thực"]

@router.post("/itinerary", summary="Khởi tạo khung lịch trình và gợi ý điểm đến thực tế từ CSDL")
def init_trip_planner(payload: ItineraryFilterRequest, db: Session = Depends(get_db)):
    city_kw = f"%{payload.city.strip()}%"
    
    # 1. Truy vấn toàn bộ điểm đến THẬT thuộc Tỉnh/Thành phố từ CSDL MySQL
    places_query = db.query(models.Destination).filter(
        models.Destination.is_active == True,
        or_(
            models.Destination.city.ilike(city_kw),
            models.Destination.address.ilike(city_kw)
        )
    )
    
    destinations = places_query.all()
    
    # Nếu thành phố chưa có nhiều dữ liệu, nạp các điểm thực tế có sẵn
    if not destinations:
        destinations = db.query(models.Destination).filter(
            models.Destination.is_active == True
        ).limit(30).all()

    # 2. Thuật toán AI tính điểm phù hợp (Matching Score) theo sở thích thực tế
    interests_lower = [i.lower() for i in payload.interests]
    scored_places = []
    
    for d in destinations:
        score = float(d.rating or 4.5) * 1.5
        
        # Phân tích theo thuộc tính CSDL thực
        if any(kw in ["thiên nhiên", "sinh thái", "biển", "rừng"] for kw in interests_lower):
            score += float(getattr(d, 'relaxation_score', 0.5) or 0.5) * 2.0
        if any(kw in ["văn hóa", "di sản", "lịch sử"] for kw in interests_lower):
            score += float(getattr(d, 'adventure_score', 0.5) or 0.5) * 1.8
        if any(kw in ["ẩm thực", "ăn uống", "chợ"] for kw in interests_lower):
            score += float(getattr(d, 'food_score', 0.5) or 0.5) * 2.0

        if payload.pace == "relax":
            score += float(getattr(d, 'relaxation_score', 0.5) or 0.5) * 1.5
        else:
            score += float(getattr(d, 'adventure_score', 0.5) or 0.5) * 1.5

        scored_places.append({
            "id": d.id,
            "destination_id": d.id,
            "name": d.name,
            "city": d.city,
            "address": f"{d.district or 'Trung tâm'}, {d.city}",
            "description": d.short_description or (d.description[:130] + "..." if d.description else "Điểm đến nổi bật."),
            "image": d.featured_image or "assets/images/anh1.jpg",
            "latitude": float(d.latitude or 16.0544),
            "longitude": float(d.longitude or 108.2022),
            "rating": round(float(d.rating or 4.8), 1),
            "estimated_cost": getattr(d, 'estimated_cost', 0) or 0,
            "ai_match_score": round(min(score / 15 * 100, 99), 1)
        })

    # Sắp xếp theo độ phù hợp AI cao nhất lên đầu
    scored_places.sort(key=lambda x: x["ai_match_score"], reverse=True)

    # 3. Tạo khung số ngày theo đúng yêu cầu người dùng (Mặc định để trống stops để người dùng tự thêm hoặc nhận gợi ý)
    itinerary_days = []
    for day_num in range(1, payload.days + 1):
        itinerary_days.append({
            "day": day_num,
            "title": f"Ngày {day_num}: Lịch trình tại {payload.city}",
            "stops": [] # Khởi tạo danh sách trống, không dùng dữ liệu mẫu
        })

    return {
        "status": "success",
        "city": payload.city,
        "total_days": payload.days,
        "pacing": payload.pace,
        "days": itinerary_days,
        "suggested_destinations": scored_places # Danh sách địa điểm thật từ CSDL đã được AI lọc
    }
class StopItemSave(BaseModel):
    day_number: int
    stop_order: int
    destination_id: Optional[int] = None
    custom_name: Optional[str] = None
    time_slot: str
    time_tag: Optional[str] = "Buổi sáng"
    custom_description: Optional[str] = ""

class TripSavePayload(BaseModel):
    user_id: Optional[int] = 1
    city: str
    total_days: int
    pacing: str
    stops: List[StopItemSave]

# 1. API LƯU LỊCH TRÌNH VÀO CƠ SỞ DỮ LIỆU MYSQL
@router.post("/save", summary="Lưu lịch trình vào CSDL MySQL")
def save_user_itinerary(payload: TripSavePayload, db: Session = Depends(get_db)):
    try:
        # Kiểm tra xem user_id có thực sự tồn tại trong bảng users không
        target_uid = payload.user_id
        if target_uid:
            user_exists = db.query(models.User).filter(models.User.id == target_uid).first()
            if not user_exists:
                target_uid = None # Nếu chưa có user thì để NULL để không bị chặn bởi khóa ngoại

        # Tạo mới bản ghi chuyến đi
        new_trip = models.UserTrip(
            user_id=target_uid,
            city=payload.city,
            total_days=payload.total_days,
            pacing=payload.pacing
        )
        db.add(new_trip)
        db.flush() # Lấy new_trip.id

        # Lưu từng điểm dừng
        for st in payload.stops:
            stop_record = models.TripStop(
                trip_id=new_trip.id,
                day_number=st.day_number,
                stop_order=st.stop_order,
                destination_id=st.destination_id,
                custom_name=st.custom_name,
                time_slot=st.time_slot,
                time_tag=st.time_tag or "Buổi sáng",
                custom_description=st.custom_description or ""
            )
            db.add(stop_record)

        db.commit()
        return {
            "status": "success",
            "trip_id": new_trip.id,
            "message": "Đã lưu lịch trình thành công vào cơ sở dữ liệu!"
        }
    except Exception as e:
        db.rollback()
        print(f"LỖI LƯU MYSQL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu: {str(e)}")

# 2. API LẤY LỊCH TRÌNH ĐÃ LƯU
# 2. API LẤY LỊCH TRÌNH ĐÃ LƯU TỪ CSDL
@router.get("/my-trip", summary="Tải lịch trình gần nhất từ CSDL")
def get_user_trip(user_id: Optional[int] = None, city: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.UserTrip)
    
    # Nếu có lọc theo thành phố
    if city:
        query = query.filter(models.UserTrip.city == city)
    
    # Nếu có user_id
    if user_id:
        query = query.filter(or_(models.UserTrip.user_id == user_id, models.UserTrip.user_id == None))
        
    # Lấy chuyến đi mới nhất được tạo
    trip = query.order_by(models.UserTrip.id.desc()).first()
    
    if not trip:
        return {"status": "empty", "message": "Chưa có lịch trình được lưu."}

    # Phân nhóm stops theo từng ngày và tính toán khoảng cách
    days_data = []
    for day_num in range(1, trip.total_days + 1):
        day_stops = []
        stops_in_day = [s for s in trip.stops if s.day_number == day_num]
        stops_in_day.sort(key=lambda x: x.stop_order)

        prev_lat = None
        prev_lon = None
        day_total_dist = 0.0

        for s in stops_in_day:
            dest = s.destination
            lat = float(dest.latitude or 16.0544) if dest else 16.0544
            lon = float(dest.longitude or 108.2022) if dest else 108.2022

            dist_from_prev = None
            if prev_lat is not None and prev_lon is not None:
                dist_from_prev = round(haversine_distance(prev_lat, prev_lon, lat, lon), 1)
                day_total_dist += dist_from_prev

            prev_lat = lat
            prev_lon = lon

            day_stops.append({
                "stop_order": s.stop_order,
                "time": s.time_slot,
                "tag": s.time_tag,
                "destination_id": s.destination_id,
                "name": dest.name if dest else s.custom_name,
                "address": f"{dest.district or 'Trung tâm'}, {dest.city}" if dest else f"{trip.city}, Việt Nam",
                "description": dest.short_description if dest else s.custom_description,
                "image": dest.featured_image if (dest and dest.featured_image) else "assets/images/anh1.jpg",
                "latitude": lat,
                "longitude": lon,
                "rating": float(dest.rating or 4.8) if dest else 5.0,
                "estimated_cost": getattr(dest, 'estimated_cost', 0) if dest else 0,
                "distance_from_prev_km": dist_from_prev
            })

        days_data.append({
            "day": day_num,
            "title": f"Ngày {day_num}: Lịch trình tại {trip.city}",
            "total_day_km": round(day_total_dist, 1),
            "stops": day_stops
        })

    return {
        "status": "success",
        "trip_id": trip.id,
        "city": trip.city,
        "total_days": trip.total_days,
        "pacing": trip.pacing,
        "days": days_data
    }