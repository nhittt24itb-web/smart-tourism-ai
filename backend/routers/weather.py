from fastapi import APIRouter, Query
from backend.services.weather_service import get_live_weather

router = APIRouter(prefix="/api/weather", tags=["Live Weather"])

@router.get("", summary="Lấy thời tiết thực tế từ vệ tinh theo thành phố")
def fetch_weather(city: str = Query("danang", description="Mã thành phố: danang, halong, dalat, phuquoc, hanoi")):
    return get_live_weather(city)