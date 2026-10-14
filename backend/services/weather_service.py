import requests
from datetime import datetime

CITY_COORDINATES = {
    "danang": {"lat": 16.0544, "lon": 108.2022, "name": "Thành Phố Đà Nẵng"},
    "halong": {"lat": 20.9505, "lon": 107.0734, "name": "Vịnh Hạ Long"},
    "dalat": {"lat": 11.9404, "lon": 108.4583, "name": "Thành Phố Đà Lạt"},
    "phuquoc": {"lat": 10.2899, "lon": 103.9840, "name": "Đảo Phú Quốc"},
    "hanoi": {"lat": 21.0285, "lon": 105.8542, "name": "Thủ Đô Hà Nội"}
}

def get_weather_icon(code: int):
    if code in [0, 1]: return "☀️"
    if code in [2, 3]: return "🌤️"
    if code in [45, 48]: return "🌫️"
    if code in [51, 53, 55, 61, 63, 65, 80, 81, 82]: return "🌧️"
    if code >= 95: return "⛈️"
    return "☀️"

def get_day_name(date_str: str, index: int):
    if index == 0: return "Hôm nay"
    try:
        # Tách chuỗi ngày an toàn
        clean_date = date_str.split("T")[0]
        dt = datetime.strptime(clean_date, "%Y-%m-%d")
        weekday_map = {0: "Th 2", 1: "Th 3", 2: "Th 4", 3: "Th 5", 4: "Th 6", 5: "Th 7", 6: "CN"}
        return weekday_map.get(dt.weekday(), "Th")
    except Exception:
        return f"Ngày {index + 1}"

def get_live_weather(city_key: str = "danang"):
    city_info = CITY_COORDINATES.get(city_key.lower(), CITY_COORDINATES["danang"])
    lat, lon = city_info["lat"], city_info["lon"]

    # Gọi trực tiếp vệ tinh Open-Meteo
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,is_day"
        f"&hourly=temperature_2m,weather_code"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        f"&timezone=Asia%2FBangkok"
    )

    try:
        res = requests.get(url, timeout=6)
        if res.status_code == 200:
            data = res.json()
            curr = data.get("current", {})
            daily = data.get("daily", {})
            hourly = data.get("hourly", {})

            # 1. Dữ liệu thời gian thực
            temp = round(curr.get("temperature_2m", 30))
            code = curr.get("weather_code", 0)
            is_day = curr.get("is_day", 1)
            icon = get_weather_icon(code)
            
            # 2. Xử lý dự báo theo giờ: Bắt đầu từ giờ hiện tại trở đi (12 tiếng kế tiếp)
            hourly_times = hourly.get("time", [])
            hourly_temps = hourly.get("temperature_2m", [])
            hourly_codes = hourly.get("weather_code", [])
            
            current_hour_int = datetime.now().hour
            hourly_list = []
            
            # Tìm vị trí mốc giờ hiện tại để không bị hiển thị giờ quá khứ
            start_index = current_hour_int if current_hour_int < len(hourly_times) else 0
            
            for j in range(start_index, min(start_index + 12, len(hourly_times))):
                hour_str = hourly_times[j].split("T")[1][:5]
                is_now = (j == start_index)
                hourly_list.append({
                    "time": "Bây giờ" if is_now else hour_str,
                    "icon": get_weather_icon(hourly_codes[j]),
                    "temp": f"{round(hourly_temps[j])}°",
                    "is_now": is_now
                })

            # 3. Dự báo 7 ngày
            daily_list = []
            daily_dates = daily.get("time", [])
            daily_max = daily.get("temperature_2m_max", [])
            daily_min = daily.get("temperature_2m_min", [])
            daily_codes = daily.get("weather_code", [])
            daily_rain = daily.get("precipitation_probability_max", [])

            for k in range(min(7, len(daily_dates))):
                daily_list.append({
                    "day": get_day_name(daily_dates[k], k),
                    "icon": get_weather_icon(daily_codes[k]),
                    "rain_prob": f"{daily_rain[k]}%" if (daily_rain and daily_rain[k] > 20) else "",
                    "temp_min": f"{round(daily_min[k])}°" if daily_min else f"{temp - 4}°",
                    "temp_max": f"{round(daily_max[k])}°" if daily_max else f"{temp + 3}°"
                })

            temp_max_today = round(daily_max[0]) if daily_max else temp + 2
            temp_min_today = round(daily_min[0]) if daily_min else temp - 4

            # Xác định trạng thái & Theme
            if code in [51, 53, 55, 61, 63, 65, 80, 81, 82, 95]:
                condition_desc = "Có mưa rải rác"
                theme = "theme-rainy"
            elif is_day == 0:
                condition_desc = "Trời quang về đêm"
                theme = "theme-night"
            elif code in [2, 3, 45, 48]:
                condition_desc = "Có mây thoáng đãng"
                theme = "theme-sunny"
            else:
                condition_desc = "Nhiều nắng & Ấm áp"
                theme = "theme-sunny"

            wind_speed = round(curr.get("wind_speed_10m", 12))

            return {
                "location": city_info["name"],
                "temp": f"{temp}°",
                "condition": condition_desc,
                "icon": icon,
                "theme": theme,
                "range": f"C:{temp_max_today}° · T:{temp_min_today}°",
                "summary": f"Thời tiết tại {city_info['name']}: {condition_desc}. Gió nhẹ {wind_speed} km/h.",
                "hourly": hourly_list,
                "daily": daily_list
            }
    except Exception as e:
        print("Lỗi khi kết nối Open-Meteo:", e)

    # Dữ liệu fallback an toàn nếu Open-Meteo timeout
    return {
        "location": city_info["name"],
        "temp": "31°",
        "condition": "Nắng nhẹ & Gió mát",
        "icon": "🌤️",
        "theme": "theme-sunny",
        "range": "C:33° · T:26°",
        "summary": f"Thời tiết ổn định tại {city_info['name']}, rất thích hợp tham quan.",
        "hourly": [
            {"time": "Bây giờ", "icon": "🌤️", "temp": "31°", "is_now": True},
            {"time": "12:00", "icon": "☀️", "temp": "33°", "is_now": False},
            {"time": "15:00", "icon": "🌤️", "temp": "32°", "is_now": False},
            {"time": "18:00", "icon": "☁️", "temp": "29°", "is_now": False}
        ],
        "daily": [
            {"day": "Hôm nay", "icon": "☀️", "temp_min": "26°", "temp_max": "33°"},
            {"day": "Th 5", "icon": "🌤️", "temp_min": "25°", "temp_max": "32°"},
            {"day": "Th 6", "icon": "🌧️", "temp_min": "24°", "temp_max": "30°"}
        ]
    }