from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import auth, destinations, recommendations, weather, trips, smart_itinerary
app = FastAPI(
    title="Smart Tourism AI API",
    version="1.0.0",
    description="Hệ thống backend du lịch thông minh ứng dụng AI và cá nhân hóa"
)

# Cấu hình CORS để Frontend kết nối không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các router vào ứng dụng
app.include_router(auth.router)
app.include_router(destinations.router)
app.include_router(recommendations.router)
app.include_router(weather.router)
app.include_router(trips.router)
app.include_router(smart_itinerary.router)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Smart Tourism AI Backend is running smoothly."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)