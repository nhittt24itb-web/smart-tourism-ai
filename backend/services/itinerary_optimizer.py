import math
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend import models

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Tính khoảng cách đường tròn lớn giữa 2 tọa độ GPS (km) theo công thức Haversine
    """
    try:
        R = 6371.0 # Bán kính trái đất (km)
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))
        delta_phi = math.radians(float(lat2) - float(lat1))
        delta_lambda = math.radians(float(lon2) - float(lon1))

        a = math.sin(delta_phi / 2.0) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return round(R * c, 2)
    except Exception:
        return 1.5

def calculate_match_score(dest: models.Destination, interests: List[str], pace: str, budget: str) -> float:
    """
    Thuật toán chấm điểm mức độ phù hợp AI (Matching Score)
    kết hợp đa tiêu chí: Rating, Gu du lịch, Nhịp độ và Ngân sách
    """
    score = float(dest.rating or 4.5) * 2.0
    interests_lower = [i.lower() for i in interests]

    rel_score = float(getattr(dest, 'relaxation_score', 0.5) or 0.5)
    adv_score = float(getattr(dest, 'adventure_score', 0.5) or 0.5)
    food_score = float(getattr(dest, 'food_score', 0.5) or 0.5)
    photo_score = float(getattr(dest, 'photography_score', 0.5) or 0.5)

    # 1. Khớp theo sở thích
    if any(k in ["thiên nhiên", "sinh thái", "biển", "rừng", "nghỉ dưỡng"] for k in interests_lower):
        score += rel_score * 3.5
    if any(k in ["văn hóa", "di sản", "lịch sử", "đền", "chùa"] for k in interests_lower):
        score += adv_score * 3.0
    if any(k in ["ẩm thực", "ăn uống", "chợ", "street food"] for k in interests_lower):
        score += food_score * 3.5
    if any(k in ["check-in", "sống ảo", "ảnh", "view đẹp"] for k in interests_lower):
        score += photo_score * 3.0
    if any(k in ["mạo hiểm", "trekking", "khám phá"] for k in interests_lower):
        score += adv_score * 3.0

    # 2. Khớp theo nhịp độ
    if pace == "relax":
        score += rel_score * 2.0
    else:
        score += adv_score * 2.0

    # 3. Khớp theo ngân sách thực tế
    cost = float(getattr(dest, 'estimated_cost', 0) or 0)
    price_level = str(getattr(dest, 'price_level', 'Medium') or 'Medium').lower()

    if budget == "Tiết kiệm":
        if cost == 0 or price_level == "low":
            score += 4.5
        elif cost > 300000:
            score -= 3.5
    elif budget == "Cao cấp":
        if cost > 250000 or price_level in ["high", "luxury"]:
            score += 4.5
        if rel_score > 0.7:
            score += 2.0
    else: # Tiêu chuẩn
        if 0 <= cost <= 600000:
            score += 2.5

    return max(score, 1.0)

def optimize_itinerary_route(
    destinations: List[models.Destination],
    days: int,
    pace: str = "relax",
    budget: str = "Tiêu chuẩn",
    interests: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Thuật toán AI phân cụm địa lý (Spatial Clustering) và tối ưu tuyến đường gần nhất (Nearest Neighbor Route)
    cho từng ngày trong lịch trình.
    """
    if interests is None:
        interests = ["Thiên nhiên", "Văn hóa", "Ẩm thực"]

    stops_per_day = 4 if pace == "active" else 3
    total_stops_needed = days * stops_per_day

    # 1. Chấm điểm toàn bộ địa điểm ứng viên
    scored_candidates = []
    for d in destinations:
        score = calculate_match_score(d, interests, pace, budget)
        scored_candidates.append({
            "dest": d,
            "id": d.id,
            "name": d.name,
            "score": score,
            "lat": float(d.latitude or 16.0544),
            "lon": float(d.longitude or 108.2022),
            "cost": float(getattr(d, 'estimated_cost', 0) or 0),
            "food_score": float(getattr(d, 'food_score', 0.5) or 0.5),
            "relaxation_score": float(getattr(d, 'relaxation_score', 0.5) or 0.5),
            "rating": round(float(d.rating or 4.8), 1),
            "address": f"{d.district or 'Trung tâm'}, {d.city}",
            "description": d.short_description or (d.description[:130] + "..." if d.description else "Điểm đến nổi bật."),
            "image": d.featured_image or "assets/images/anh1.jpg"
        })

    scored_candidates.sort(key=lambda x: x["score"], reverse=True)

    # 2. Phân bổ các điểm vào từng ngày theo Cụm Không Gian & Khoảng Cách Gần Nhất
    assigned_ids = set()
    itinerary_days = []

    time_slots_relax = [
        {"time": "08:30 - 10:30", "tag": "Buổi sáng"},
        {"time": "14:00 - 16:30", "tag": "Buổi chiều"},
        {"time": "18:30 - 21:00", "tag": "Buổi tối"}
    ]
    time_slots_active = [
        {"time": "08:00 - 09:45", "tag": "Buổi sáng"},
        {"time": "10:15 - 12:00", "tag": "Buổi trưa"},
        {"time": "14:00 - 16:30", "tag": "Buổi chiều"},
        {"time": "18:30 - 21:00", "tag": "Buổi tối"}
    ]
    time_slots = time_slots_active if pace == "active" else time_slots_relax

    for day_num in range(1, days + 1):
        day_stops = []
        available_pool = [c for c in scored_candidates if c["id"] not in assigned_ids]
        
        if not available_pool:
            # Nếu hết ứng viên mới, cho phép tái sử dụng
            available_pool = scored_candidates[:]

        # Điểm mỏ neo (Anchor) của ngày: Điểm có điểm số AI cao nhất
        anchor = available_pool[0]
        assigned_ids.add(anchor["id"])

        # Tìm các điểm lân cận gần anchor nhất cho ngày này
        day_cluster = [anchor]
        other_candidates = [c for c in available_pool if c["id"] != anchor["id"]]
        
        # Sắp xếp các điểm còn lại theo khoảng cách tới anchor kết hợp độ phù hợp
        other_candidates.sort(key=lambda c: (
            haversine_distance(anchor["lat"], anchor["lon"], c["lat"], c["lon"]) * 0.7 - c["score"] * 0.3
        ))

        needed_more = min(stops_per_day - 1, len(other_candidates))
        for i in range(needed_more):
            day_cluster.append(other_candidates[i])
            assigned_ids.add(other_candidates[i]["id"])

        # 3. Sắp xếp thứ tự các điểm trong ngày theo Thuật Toán Nearest Neighbor
        # Buổi tối ưu tiên ẩm thực / chợ / phố đi bộ nếu có
        evening_candidates = [c for c in day_cluster if c["food_score"] > 0.6 or "chợ" in c["name"].lower() or "đêm" in c["name"].lower()]
        evening_stop = evening_candidates[0] if evening_candidates else None
        
        remaining_for_route = [c for c in day_cluster if c != evening_stop]
        
        ordered_stops = []
        current_node = remaining_for_route[0] if remaining_for_route else day_cluster[0]
        ordered_stops.append(current_node)
        unvisited = [c for c in remaining_for_route if c != current_node]

        while unvisited:
            next_node = min(unvisited, key=lambda c: haversine_distance(current_node["lat"], current_node["lon"], c["lat"], c["lon"]))
            ordered_stops.append(next_node)
            unvisited.remove(next_node)
            current_node = next_node

        if evening_stop:
            ordered_stops.append(evening_stop)

        # 4. Gắn khung giờ và tính khoảng cách di chuyển giữa các trạm
        day_total_km = 0.0
        for idx, stop_item in enumerate(ordered_stops):
            slot = time_slots[idx] if idx < len(time_slots) else {"time": "19:00 - 21:00", "tag": "Buổi tối"}
            
            # Khoảng cách từ trạm trước đó
            dist_from_prev = 0.0
            if idx > 0:
                prev_stop = ordered_stops[idx - 1]
                dist_from_prev = haversine_distance(prev_stop["lat"], prev_stop["lon"], stop_item["lat"], stop_item["lon"])
                day_total_km += dist_from_prev

            day_stops.append({
                "stop_order": idx + 1,
                "time": slot["time"],
                "tag": slot["tag"],
                "destination_id": stop_item["id"],
                "name": stop_item["name"],
                "address": stop_item["address"],
                "description": stop_item["description"],
                "image": stop_item["image"],
                "latitude": stop_item["lat"],
                "longitude": stop_item["lon"],
                "rating": stop_item["rating"],
                "estimated_cost": stop_item["cost"],
                "ai_match_score": round(min(stop_item["score"] / 20.0 * 100.0, 99.0), 1),
                "distance_from_prev_km": dist_from_prev
            })

        itinerary_days.append({
            "day": day_num,
            "title": f"Ngày {day_num}: Lịch trình tối ưu khoảng cách",
            "total_day_km": round(day_total_km, 1),
            "stops": day_stops
        })

    # Toàn bộ danh sách gợi ý kèm điểm khớp
    all_suggestions = []
    for c in scored_candidates:
        all_suggestions.append({
            "id": c["id"],
            "destination_id": c["id"],
            "name": c["name"],
            "address": c["address"],
            "description": c["description"],
            "image": c["image"],
            "latitude": c["lat"],
            "longitude": c["lon"],
            "rating": c["rating"],
            "estimated_cost": c["cost"],
            "ai_match_score": round(min(c["score"] / 20.0 * 100.0, 99.0), 1)
        })

    return {
        "days": itinerary_days,
        "suggested_destinations": all_suggestions
    }

def classify_destination_type(dest) -> str:
    """
    Phân loại chuẩn xác loại hình điểm đến:
    - ACCOMMODATION: Khách sạn, Resort, Villa, Homestay, Lưu trú
    - DINING: Ẩm thực, Nhà hàng, Quán ăn, Cà phê, Quán đặc sản
    - ATTRACTION: Điểm tham quan, Danh thắng, Khu du lịch, Văn hóa, Thiên nhiên, Công viên
    """
    text = (str(dest.name or "") + " " + str(dest.short_description or "") + " " + str(dest.description or "")).lower()
    
    # 1. ACCOMMODATION
    hotel_keys = [
        "hotel", "khách sạn", "resort", "villa", "homestay", "riverside", "hostel",
        "boutique", "retreat", "lodge", "stay", "suites", "wings house", "rose homestay",
        "hyatt", "pullman", "intercontinental", "naman retreat", "marriott", "almanity",
        "four seasons", "vinpearl resort", "sea garden"
    ]
    if any(k in text for k in hotel_keys):
        return "ACCOMMODATION"

    # 2. DINING
    dining_keys = [
        "quán", "nhà hàng", "mì ", "mì quảng", "bún", "bánh mì", "bánh xèo", "bánh bèo", "bánh canh",
        "bánh đập", "cơm", "phở", "chè", "bếp", "ốc", "lẩu", "nướng", "cafe", "cà phê", "coffee",
        "ẩm thực", "ăn vặt", "hải sản", "cao lầu", "buffet", "đặc sản", "hoa hồng trắng", "uống",
        "trà sữa", "ăn sáng", "ăn tối", "chợ đêm"
    ]
    if any(k in text for k in dining_keys):
        return "DINING"

    # 3. ATTRACTION
    return "ATTRACTION"

def find_similar_destinations(
    db: Session,
    target_dest_id: int,
    city: str,
    budget: str = "Tiêu chuẩn",
    exclude_ids: Optional[List[int]] = None,
    limit: int = 6
) -> List[Dict[str, Any]]:
    """
    Tìm kiếm các địa điểm tương đồng:
    1. CÙNG LOẠI HÌNH (Tham quan đổi tham quan, Ẩm thực đổi ẩm thực, không bị đổi sang khách sạn)
    2. PHÙ HỢP VỚI GIÁ (So khớp mức giá gốc và ngân sách đã chọn)
    3. GẦN NHẤT (Tối ưu cự ly di chuyển)
    """
    if exclude_ids is None:
        exclude_ids = []

    target_dest = db.query(models.Destination).filter(models.Destination.id == target_dest_id).first()
    if not target_dest:
        return []

    target_lat = float(target_dest.latitude or 16.0544)
    target_lon = float(target_dest.longitude or 108.2022)
    target_cost = float(target_dest.estimated_cost or 0)
    target_type = classify_destination_type(target_dest)

    # Lấy các điểm đến cùng thành phố
    city_kw = f"%{city.strip()}%"
    candidates = db.query(models.Destination).filter(
        models.Destination.is_active == True,
        models.Destination.id != target_dest_id,
        or_(
            models.Destination.city.ilike(city_kw),
            models.Destination.address.ilike(city_kw)
        )
    ).all()

    if not candidates:
        candidates = db.query(models.Destination).filter(
            models.Destination.is_active == True,
            models.Destination.id != target_dest_id
        ).limit(50).all()

    # Lọc nghiêm ngặt: Chỉ lấy các điểm CÙNG THỂ LOẠI (Attraction / Dining / Accommodation)
    same_type_candidates = [c for c in candidates if classify_destination_type(c) == target_type and c.id not in exclude_ids]
    
    # Nếu trong cùng thành phố không đủ cùng thể loại thì mở rộng tìm kiếm
    if len(same_type_candidates) < 2:
        same_type_candidates = [c for c in candidates if c.id not in exclude_ids]

    results = []
    for c in same_type_candidates:
        c_lat = float(c.latitude or 16.0544)
        c_lon = float(c.longitude or 108.2022)
        c_cost = float(c.estimated_cost or 0)
        c_type = classify_destination_type(c)
        dist_km = haversine_distance(target_lat, target_lon, c_lat, c_lon)

        # 1. So khớp GIÁ (Price Proximity Score)
        diff_price = abs(c_cost - target_cost)
        if target_cost == 0 and c_cost == 0:
            price_score = 1.0
        elif target_cost > 0 and c_cost > 0:
            denom = max(c_cost, target_cost, 150000.0)
            price_score = max(0.0, 1.0 - (diff_price / denom))
        elif target_cost == 0 and c_cost <= 100000:
            price_score = 0.75
        elif target_cost == 0 and c_cost > 500000:
            price_score = 0.2
        else:
            price_score = 0.5

        # 2. Phù hợp với mức NGÂN SÁCH đã chọn (Budget Tier Score)
        if budget == "Tiết kiệm":
            if c_cost <= 100000:
                budget_score = 1.0
            elif c_cost <= 300000:
                budget_score = 0.7
            else:
                budget_score = 0.2
        elif budget == "Cao cấp":
            if c_cost >= 500000:
                budget_score = 1.0
            else:
                budget_score = 0.7
        else: # Tiêu chuẩn
            if c_cost <= 500000:
                budget_score = 1.0
            elif c_cost <= 1000000:
                budget_score = 0.7
            else:
                budget_score = 0.4

        # 3. Khoảng cách địa lý (Geographic Proximity Score)
        geo_score = max(0.0, 1.0 - (dist_km / 35.0))

        # 4. Điểm đánh giá (Rating Score)
        rating_score = min(1.0, float(c.rating or 4.5) / 5.0)

        # Tổng hợp điểm phù hợp (Weighted Similarity)
        # Giá và Thể loại và Khoảng cách là quan trọng nhất
        match_score = (
            0.40 * price_score +
            0.35 * geo_score +
            0.15 * budget_score +
            0.10 * rating_score
        )

        similarity_percent = round(min(99.0, max(55.0, 50.0 + match_score * 49.0)), 1)

        # Chênh lệch giá chi tiết
        price_delta = c_cost - target_cost
        if price_delta == 0:
            price_comparison_text = f"Giá tương đương ({c_cost:,.0f} đ)" if c_cost > 0 else "Cùng miễn phí vé"
            price_badge_type = "equal"
        elif price_delta < 0:
            price_comparison_text = f"Tiết kiệm hơn (-{abs(price_delta):,.0f} đ)"
            price_badge_type = "cheaper"
        else:
            price_comparison_text = f"Giá cao hơn (+{price_delta:,.0f} đ)"
            price_badge_type = "higher"

        # Tên nhãn thể loại
        type_badge_label = "🏛️ Điểm tham quan" if c_type == "ATTRACTION" else ("🍜 Ẩm thực" if c_type == "DINING" else "🏨 Khách sạn / Nghỉ dưỡng")

        # Lý do gợi ý
        reasons = [type_badge_label]
        if dist_km <= 5.0:
            reasons.append(f"Gần điểm cũ ({dist_km} km)")
        else:
            reasons.append(f"Cách {dist_km} km")
        reasons.append(price_comparison_text)

        results.append({
            "id": c.id,
            "destination_id": c.id,
            "name": c.name,
            "address": f"{c.district or 'Trung tâm'}, {c.city}",
            "description": c.short_description or (c.description[:120] + "..." if c.description else ""),
            "image": c.featured_image or "assets/images/anh1.jpg",
            "latitude": c_lat,
            "longitude": c_lon,
            "rating": round(float(c.rating or 4.8), 1),
            "estimated_cost": c_cost,
            "distance_km": dist_km,
            "category_type": c_type,
            "category_label": type_badge_label,
            "price_comparison_text": price_comparison_text,
            "price_badge_type": price_badge_type,
            "price_delta": price_delta,
            "similarity_percent": similarity_percent,
            "similarity_reason": " • ".join(reasons)
        })

    # Sắp xếp ưu tiên: Điểm số kết hợp cao nhất (gần + hợp giá + hợp gu)
    results.sort(key=lambda x: (x["similarity_percent"] - (x["distance_km"] * 0.8)), reverse=True)
    return results[:limit]
