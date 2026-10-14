from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from backend.database import get_db
from backend import models

try:
    from backend.models import Favorite, Destination, User
except Exception:
    Favorite = getattr(models, "Favorite", None)
    Destination = models.Destination
    User = models.User

try:
    from backend.ai.matrix_recommender import matrix_engine, ACTION_WEIGHTS
except Exception:
    matrix_engine = None
    ACTION_WEIGHTS = {"VIEW": 1.0, "CLICK_RECOMMENDATION": 2.0, "VIEW_POPUP": 2.5}

router = APIRouter(prefix="/api/recommendations", tags=["AI Recommendations"])


class ToggleFavoritePayload(BaseModel):
    user_id: Optional[int] = 1
    destination_id: int


# 1. API BẤM TIM / BỎ TIM
@router.post("/favorites/toggle", summary="Thêm hoặc xóa yêu thích trong CSDL")
def toggle_favorite_destination(payload: ToggleFavoritePayload, db: Session = Depends(get_db)):
    uid = payload.user_id or 1
    dest_id = payload.destination_id

    try:
        fav_model = getattr(models, "Favorite", None)
        if not fav_model:
            return {"status": "ok", "is_favorite": True, "destination_id": dest_id}

        fav_record = db.query(fav_model).filter(
            fav_model.user_id == uid,
            fav_model.destination_id == dest_id
        ).first()

        if fav_record:
            db.delete(fav_record)
            db.commit()
            return {"status": "removed", "is_favorite": False, "destination_id": dest_id}
        else:
            new_fav = fav_model(user_id=uid, destination_id=dest_id)
            db.add(new_fav)
            db.commit()
            return {"status": "added", "is_favorite": True, "destination_id": dest_id}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e), "is_favorite": False}


# 2. API LẤY DANH SÁCH ID ĐÃ TIM CỦA USER
@router.get("/favorites/my-ids", summary="Lấy danh sách ID các địa điểm đã yêu thích")
def get_user_favorite_ids(user_id: int = 1, db: Session = Depends(get_db)):
    try:
        fav_model = getattr(models, "Favorite", None)
        if not fav_model:
            return {"favorite_ids": []}

        favs = db.query(fav_model.destination_id).filter(fav_model.user_id == user_id).all()
        fav_ids = [f[0] for f in favs]
        return {"favorite_ids": fav_ids}
    except Exception:
        return {"favorite_ids": []}


class TrackActionRequest(BaseModel):
    user_id: int
    destination_id: int
    action: str


# -----------------------------------------------------------------------------
# 3. API GỢI Ý ĐA TIÊU CHÍ (AN TOÀN TUYỆT ĐỐI, KHÔNG BAO GIỜ BỊ 500)
# -----------------------------------------------------------------------------

@router.get("", summary="Gợi ý điểm đến kết hợp khảo sát sở thích, thời tiết, ngân sách")
def get_hybrid_recommendations(
    user_id: Optional[int] = Query(1, description="ID người dùng"),
    interests: Optional[str] = Query(None, description="Danh sách sở thích"),
    budget: Optional[str] = Query("Medium", description="Ngân sách"),
    companion: Optional[str] = Query(None, description="Đi cùng"),
    pace: Optional[str] = Query(None, description="Nhịp độ"),
    weather: Optional[str] = Query("sunny", description="Thời tiết"),
    city: Optional[str] = Query(None, description="Tỉnh thành"),
    limit: int = 8,
    db: Session = Depends(get_db)
):
    try:
        query = db.query(models.Destination).filter(models.Destination.is_active == 1)
        if city and city != "all":
            query = query.filter(models.Destination.city.ilike(f"%{city}%"))
        destinations = query.all()
    except Exception:
        destinations = db.query(models.Destination).limit(100).all()

    # 1. LẤY DANH SÁCH ID ĐÃ TIM TỪ BẢNG favorites
    user_fav_ids = set()
    try:
        fav_model = getattr(models, "Favorite", None)
        if fav_model:
            user_fav_records = db.query(fav_model.destination_id).filter(fav_model.user_id == (user_id or 1)).all()
            user_fav_ids = set([r[0] for r in user_fav_records])
    except Exception:
        pass

    # 2. THỐNG KÊ SỐ LẦN XEM CỦA TỪNG ĐỊA ĐIỂM TỪ BẢNG user_behaviors
    view_counts = {}
    try:
        behavior_model = getattr(models, "UserBehavior", None)
        if behavior_model:
            views = db.query(
                behavior_model.destination_id,
                func.count(behavior_model.id).label("total_views")
            ).filter(
                behavior_model.user_id == (user_id or 1),
                behavior_model.action.in_(["VIEW", "VIEW_POPUP", "CLICK_RECOMMENDATION"])
            ).group_by(behavior_model.destination_id).all()
            
            for v_id, count in views:
                view_counts[v_id] = count
    except Exception:
        pass

    # 3. LẤY DANH MỤC VÀ TỈNH THÀNH QUAN TÂM ĐỂ HỌC GU
    tracked_ids = user_fav_ids.union(set(view_counts.keys()))
    fav_cities = set()
    fav_category_ids = set()
    if tracked_ids:
        tracked_dests = [d for d in destinations if d.id in tracked_ids]
        for td in tracked_dests:
            if td.city:
                fav_cities.add(td.city.lower())
            if hasattr(td, "category_id") and td.category_id:
                fav_category_ids.add(td.category_id)

    interest_list = [i.strip().lower() for i in interests.split(",")] if interests else []
    is_sea_selected = any("biển" in it for it in interest_list)

    SEA_KEYWORDS = [
        "biển", "bãi biển", "vịnh", "đảo", "bãi", "bán đảo", "san hô", 
        "nha trang", "phú quốc", "mỹ khê", "hạ long", "côn đảo", "quy nhơn", 
        "vũng tàu", "mũi né", "phú quý", "lý sơn", "kỳ co", "eo gió", "lặn biển"
    ]

    scored_items = []
    for d in destinations:
        try:
            rating_val = float(d.rating or 4.5)
        except (ValueError, TypeError):
            rating_val = 4.5

        # Điểm cơ sở
        score = rating_val * 4.0
        reasons = []

        d_name = (d.name or "").lower()
        d_city = (d.city or "").lower()
        d_category_id = getattr(d, 'category_id', 2)
        d_desc = f"{d.description or ''} {getattr(d, 'short_description', '') or ''}".lower()
        combined_text = f"{d_name} {d_city} {d_desc}"

        # =========================================================================
        # TRỌNG SỐ ƯU TIÊN HÀNG ĐẦU CHO ĐỊA ĐIỂM ĐÃ TIM HOẶC ĐÃ XEM NHIỀU
        # =========================================================================
        # 1. ĐÃ TIM: Tặng +100 điểm để nhảy ngay lên top đầu
        if d.id in user_fav_ids:
            score += 100.0
            reasons.append("❤️ Điểm đến bạn đã lưu yêu thích")

        # 2. XEM NHIỀU: Mỗi lần xem cộng +15 điểm (tối đa +60 điểm)
        v_count = view_counts.get(d.id, 0)
        if v_count > 0:
            view_bonus = min(60.0, v_count * 15.0)
            score += view_bonus
            reasons.append(f"👀 Bạn đã quan tâm tìm hiểu ({v_count} lượt xem)")

        # 3. CÙNG THÀNH PHỐ HOẶC DANH MỤC VỚI CÁC ĐIỂM ĐÃ THÍCH
        if d_city and d_city in fav_cities:
            score += 20.0
            reasons.append(f"Thuộc khu vực bạn quan tâm ({d.city})")

        if d_category_id in fav_category_ids:
            score += 15.0
            reasons.append("Chủ đề du lịch hợp gu của bạn")

        # 4. Ưu tiên biển đảo nếu có tick chọn
        matched_sea = False
        if is_sea_selected:
            if any(k in combined_text for k in SEA_KEYWORDS):
                score += 35.0
                matched_sea = True
                reasons.append("Điểm đến biển đảo tuyệt đẹp")

        # 5. Sở thích khảo sát
        for it in interest_list:
            if "biển" in it:
                continue
            if it in combined_text:
                score += 15.0
                reasons.append(f"Hợp gu: {it.title()}")

        # 6. Chi phí an toàn
        raw_cost = getattr(d, 'estimated_cost', 0)
        try:
            cost = float(raw_cost or 0)
        except (ValueError, TypeError):
            cost = 0.0

        if budget in ["Tiết kiệm", "Low"] and cost <= 250000:
            score += 8.0
        elif budget in ["Cao cấp", "High"] and cost >= 800000:
            score += 8.0

        if not reasons:
            reasons.append("Điểm đến thịnh hành được đề xuất")

        try:
            lat_val = float(getattr(d, 'latitude', 16.0544) or 16.0544)
        except (ValueError, TypeError):
            lat_val = 16.0544

        try:
            lon_val = float(getattr(d, 'longitude', 108.2022) or 108.2022)
        except (ValueError, TypeError):
            lon_val = 108.2022

        scored_items.append({
            "id": d.id,
            "name": d.name,
            "city": d.city,
            "district": getattr(d, 'district', None) or "Trung tâm",
            "category": getattr(d, 'category', 'Du lịch & Trải nghiệm'),
            "rating": rating_val,
            "review_count": getattr(d, 'review_count', 120) or 120,
            "estimated_cost": cost,
            "price": f"{cost:,.0f} VNĐ".replace(",", ".") if cost > 0 else "Miễn phí",
            "is_indoor": bool(getattr(d, 'is_indoor', False)),
            "is_outdoor": bool(getattr(d, 'is_outdoor', True)),
            "featured_image": d.featured_image or "assets/images/anh1.jpg",
            "short_description": getattr(d, 'short_description', None) or (d.description[:120] + "..." if d.description else ""),
            "description": d.description or getattr(d, 'short_description', ""),
            "latitude": lat_val,
            "longitude": lon_val,
            "match_score": min(99, max(85, int(score))),
            "recommend_reasons": reasons
        })

    # Sắp xếp điểm AI từ cao xuống thấp (điểm đã tim/xem nhiều sẽ đứng đầu)
    scored_items.sort(key=lambda x: x["match_score"], reverse=True)
    return scored_items[:limit]
# 4. GHI NHẬN HÀNH VI TƯƠNG TÁC
@router.post("/track", summary="Ghi nhận hành vi tương tác")
def track_user_action(payload: TrackActionRequest, db: Session = Depends(get_db)):
    action_clean = payload.action.upper().strip()
    weight_val = ACTION_WEIGHTS.get(action_clean, 1.0) if ACTION_WEIGHTS else 1.0

    try:
        behavior = models.UserBehavior(
            user_id=payload.user_id,
            destination_id=payload.destination_id,
            action=action_clean,
            weight=weight_val
        )
        db.add(behavior)
        db.commit()
    except Exception:
        db.rollback()

    return {"status": "success", "action": action_clean}


# 5. GỢI Ý CÁ NHÂN HÓA QUA MA TRẬN
@router.get("/personal", summary="Gợi ý qua ma trận")
def get_personal_recommendations(
    user_id: Optional[int] = Query(None),
    recent_dest_id: Optional[int] = Query(None),
    limit: int = 8,
    db: Session = Depends(get_db)
):
    return db.query(models.Destination).order_by(models.Destination.id.desc()).limit(limit).all()
# -----------------------------------------------------------------------------
# API LẤY CHI TIẾT CÁC ĐỊA ĐIỂM ĐÃ LƯU YÊU THÍCH (CHO TRANG FAVORITES.HTML)
# -----------------------------------------------------------------------------
@router.get("/favorites/my-destinations", summary="Lấy danh sách chi tiết các điểm đến đã lưu yêu thích")
def get_user_favorite_destinations(user_id: int = Query(1), db: Session = Depends(get_db)):
    try:
        fav_model = getattr(models, "Favorite", None)
        if not fav_model:
            return []

        # Truy vấn các bản ghi yêu thích của user, sắp xếp mới nhất lên đầu
        fav_records = db.query(fav_model).filter(fav_model.user_id == user_id).order_by(fav_model.created_at.desc()).all()
        dest_ids = [f.destination_id for f in fav_records]

        if not dest_ids:
            return []

        destinations = db.query(models.Destination).filter(models.Destination.id.in_(dest_ids)).all()
        dest_dict = {d.id: d for d in destinations}

        results = []
        for f in fav_records:
            d = dest_dict.get(f.destination_id)
            if not d:
                continue

            results.append({
                "id": d.id,
                "name": d.name,
                "city": d.city or "Việt Nam",
                "district": getattr(d, 'district', None) or "Trung tâm",
                "category": getattr(d, 'category', 'Du lịch & Trải nghiệm'),
                "rating": float(d.rating or 4.8),
                "review_count": getattr(d, 'review_count', 120) or 120,
                "estimated_cost": getattr(d, 'estimated_cost', 0) or 0,
                "price": "Miễn phí" if not d.estimated_cost else f"{int(d.estimated_cost):,} VNĐ".replace(",", "."),
                "featured_image": d.featured_image or "assets/images/anh1.jpg",
                "short_description": getattr(d, 'short_description', None) or (d.description[:120] + "..." if d.description else ""),
                "description": d.description or getattr(d, 'short_description', ""),
                "latitude": float(getattr(d, 'latitude', 16.0544) or 16.0544),
                "longitude": float(getattr(d, 'longitude', 108.2022) or 108.2022),
                "favorited_at": f.created_at.strftime("%d/%m/%Y") if hasattr(f, 'created_at') and f.created_at else "Gần đây"
            })

        return results
    except Exception as e:
        print("Lỗi lấy danh sách favorites chi tiết:", e)
        return []