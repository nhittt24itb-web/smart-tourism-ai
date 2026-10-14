from pydantic import BaseModel
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend.database import get_db
from backend import models
from backend.services.itinerary_optimizer import (
    haversine_distance,
    optimize_itinerary_route,
    find_similar_destinations
)

router = APIRouter(prefix="/api/trips", tags=["Smart AI Itinerary"])

class SmartItineraryRequest(BaseModel):
    user_id: Optional[int] = 1
    city: str = "Đà Nẵng"
    days: int = 3
    pace: str = "relax"          # "relax" (3 stops) hoặc "active" (4 stops)
    budget: str = "Tiêu chuẩn"   # "Tiết kiệm", "Tiêu chuẩn", "Cao cấp"
    interests: List[str] = ["Thiên nhiên", "Văn hóa", "Ẩm thực"]
    auto_save: bool = True

class ReplaceStopRequest(BaseModel):
    trip_id: Optional[int] = None
    day_number: int
    stop_order: int
    old_destination_id: Optional[int] = None
    new_destination_id: int
    user_id: Optional[int] = 1

# 1. API TỐI ƯU HÓA LỊCH TRÌNH THÔNG MINH (KHOẢNG CÁCH NGẮN NHẤT + GU + NGÂN SÁCH + TỰ ĐỘNG LƯU MYSQL)
@router.post("/optimize", summary="Tối ưu hóa lịch trình tự động bằng thuật toán AI và lưu vào CSDL")
def optimize_smart_trip(payload: SmartItineraryRequest, db: Session = Depends(get_db)):
    city_kw = f"%{payload.city.strip()}%"

    # Lấy các điểm đến thật từ MySQL
    destinations = db.query(models.Destination).filter(
        models.Destination.is_active == True,
        or_(
            models.Destination.city.ilike(city_kw),
            models.Destination.address.ilike(city_kw)
        )
    ).all()

    if not destinations:
        destinations = db.query(models.Destination).filter(
            models.Destination.is_active == True
        ).limit(40).all()

    # Chạy thuật toán tối ưu hóa phân cụm địa lý và Nearest Neighbor
    result = optimize_itinerary_route(
        destinations=destinations,
        days=payload.days,
        pace=payload.pace,
        budget=payload.budget,
        interests=payload.interests
    )

    trip_id = None
    if payload.auto_save:
        try:
            # Kiểm tra user_id
            target_uid = payload.user_id
            if target_uid:
                u = db.query(models.User).filter(models.User.id == target_uid).first()
                if not u:
                    target_uid = None

            new_trip = models.UserTrip(
                user_id=target_uid,
                city=payload.city,
                total_days=payload.days,
                pacing=payload.pace
            )
            db.add(new_trip)
            db.flush()
            trip_id = new_trip.id

            # Lưu từng điểm dừng đã được tối ưu vào MySQL
            for day_data in result["days"]:
                for st in day_data["stops"]:
                    stop_record = models.TripStop(
                        trip_id=new_trip.id,
                        day_number=day_data["day"],
                        stop_order=st["stop_order"],
                        destination_id=st["destination_id"],
                        time_slot=st["time"],
                        time_tag=st["tag"],
                        custom_description=st.get("description", "")
                    )
                    db.add(stop_record)

            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Lỗi lưu tự động lịch trình: {e}")

    return {
        "status": "success",
        "trip_id": trip_id,
        "city": payload.city,
        "total_days": payload.days,
        "pacing": payload.pace,
        "budget": payload.budget,
        "interests": payload.interests,
        "days": result["days"],
        "suggested_destinations": result["suggested_destinations"]
    }

# 2. API TÌM KIẾM ĐỊA ĐIỂM TƯƠNG TỰ (ĐỒNG THỂ LOẠI + GẦN NHẤT + HỢP NGÂN SÁCH)
@router.get("/similar-destinations", summary="Gợi ý các địa điểm tương tự khi muốn đổi điểm đến")
def get_similar_destinations(
    destination_id: int = Query(...),
    city: str = Query("Đà Nẵng"),
    budget: str = Query("Tiêu chuẩn"),
    exclude_ids: str = Query(""),
    db: Session = Depends(get_db)
):
    excluded = []
    if exclude_ids:
        try:
            excluded = [int(x) for x in exclude_ids.split(",") if x.strip().isdigit()]
        except Exception:
            excluded = []

    similar_items = find_similar_destinations(
        db=db,
        target_dest_id=destination_id,
        city=city,
        budget=budget,
        exclude_ids=excluded,
        limit=6
    )

    target_dest = db.query(models.Destination).filter(models.Destination.id == destination_id).first()
    target_info = None
    if target_dest:
        from backend.services.itinerary_optimizer import classify_destination_type
        t_type = classify_destination_type(target_dest)
        t_cat_label = "🏛️ Điểm tham quan" if t_type == "ATTRACTION" else ("🍜 Điểm ẩm thực" if t_type == "DINING" else "🏨 Khách sạn / Nghỉ dưỡng")
        t_cost = float(target_dest.estimated_cost or 0)
        target_info = {
            "name": target_dest.name,
            "cost": t_cost,
            "category_type": t_type,
            "category_label": t_cat_label,
            "formatted_cost": f"{t_cost:,.0f} đ" if t_cost > 0 else "Miễn phí vé"
        }

    return {
        "status": "success",
        "target_destination_id": destination_id,
        "target_info": target_info,
        "similar_destinations": similar_items
    }

# 3. API THAY THẾ ĐIỂM DỪNG VÀ CẬP NHẬT CƠ SỞ DỮ LIỆU
@router.post("/replace-stop", summary="Thay thế điểm dừng trong lịch trình và đồng bộ CSDL")
def replace_trip_stop(payload: ReplaceStopRequest, db: Session = Depends(get_db)):
    new_dest = db.query(models.Destination).filter(models.Destination.id == payload.new_destination_id).first()
    if not new_dest:
        raise HTTPException(status_code=404, detail="Không tìm thấy địa điểm mới trong hệ thống")

    if payload.trip_id:
        try:
            stop = db.query(models.TripStop).filter(
                models.TripStop.trip_id == payload.trip_id,
                models.TripStop.day_number == payload.day_number,
                models.TripStop.stop_order == payload.stop_order
            ).first()

            if stop:
                stop.destination_id = new_dest.id
                stop.custom_name = new_dest.name
                stop.custom_description = new_dest.short_description or new_dest.description
                db.commit()
            else:
                # Nếu chưa có bản ghi thì thêm mới
                new_stop = models.TripStop(
                    trip_id=payload.trip_id,
                    day_number=payload.day_number,
                    stop_order=payload.stop_order,
                    destination_id=new_dest.id,
                    time_slot="10:00 - 12:00",
                    time_tag="Đã thay đổi",
                    custom_description=new_dest.short_description or new_dest.description
                )
                db.add(new_stop)
                db.commit()
        except Exception as e:
            db.rollback()
            print(f"Lỗi cập nhật CSDL khi đổi điểm: {e}")

    return {
        "status": "success",
        "message": f"Đã thay thế thành công bằng {new_dest.name}",
        "new_stop": {
            "destination_id": new_dest.id,
            "name": new_dest.name,
            "address": f"{new_dest.district or 'Trung tâm'}, {new_dest.city}",
            "description": new_dest.short_description or (new_dest.description[:130] if new_dest.description else ""),
            "image": new_dest.featured_image or "assets/images/anh1.jpg",
            "latitude": float(new_dest.latitude or 16.0544),
            "longitude": float(new_dest.longitude or 108.2022),
            "rating": round(float(new_dest.rating or 4.8), 1),
            "estimated_cost": float(getattr(new_dest, 'estimated_cost', 0) or 0)
        }
    }
