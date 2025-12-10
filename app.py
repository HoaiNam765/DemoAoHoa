from flask import Flask, render_template, request, jsonify
import requests
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)

API_KEY = "616e47c842405551609b22f93aa0d6cf"  # TODO: THAY bằng API key OpenWeatherMap của bạn
CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
GEO_URL = "http://api.openweathermap.org/geo/1.0/direct"


def get_current_weather(city=None, lat=None, lon=None):
    params = {
        "appid": API_KEY,
        "units": "metric",
        "lang": "vi"
    }
    if city:
        params["q"] = city
    else:
        params["lat"] = lat
        params["lon"] = lon

    r = requests.get(CURRENT_URL, params=params)
    return r.json()


def get_forecast(city=None, lat=None, lon=None):
    params = {
        "appid": API_KEY,
        "units": "metric",
        "lang": "vi"
    }
    if city:
        params["q"] = city
    else:
        params["lat"] = lat
        params["lon"] = lon

    r = requests.get(FORECAST_URL, params=params)
    return r.json()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/weather")
def api_weather():
    """
    Trả về JSON: thời tiết hiện tại + dự báo 5 ngày + dữ liệu giờ để vẽ biểu đồ.
    Nhận:
      - city (tên thành phố) HOẶC
      - lat, lon (từ GPS)
    """
    city = request.args.get("city")
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if not city and not (lat and lon):
        return jsonify({"error": "Thiếu tham số city hoặc lat/lon"}), 400

    try:
        if city:
            current = get_current_weather(city=city)
            forecast = get_forecast(city=city)
        else:
            current = get_current_weather(lat=lat, lon=lon)
            forecast = get_forecast(lat=lat, lon=lon)
    except Exception as e:
        return jsonify({"error": "Không thể gọi API thời tiết", "detail": str(e)}), 500

    if current.get("cod") != 200:
        return jsonify({"error": "Không tìm thấy thành phố"}), 404

    # Xử lý current
    current_data = {
        "city": current["name"],
        "country": current["sys"].get("country", ""),
        "temp": current["main"]["temp"],
        "feels_like": current["main"]["feels_like"],
        "humidity": current["main"]["humidity"],
        "pressure": current["main"]["pressure"],
        "wind_speed": current["wind"]["speed"],
        "description": current["weather"][0]["description"],
        "main": current["weather"][0]["main"],  # Clear, Clouds, Rain,...
        "icon": current["weather"][0]["icon"],
        "sunrise": current["sys"]["sunrise"],
        "sunset": current["sys"]["sunset"],
    }

    # ====== Xử lý forecast 5 ngày (lấy min/max mỗi ngày) ======
    daily = defaultdict(lambda: {"temps": [], "icons": [], "descs": []})
    hourly_points = []

    for idx, item in enumerate(forecast.get("list", [])):
        dt = datetime.fromtimestamp(item["dt"])
        date_key = dt.date().isoformat()
        temp = item["main"]["temp"]
        desc = item["weather"][0]["description"]
        icon = item["weather"][0]["icon"]

        daily[date_key]["temps"].append(temp)
        daily[date_key]["icons"].append(icon)
        daily[date_key]["descs"].append(desc)

        # lấy ~8 điểm đầu (24h tới) cho biểu đồ
        if idx < 8:
            hourly_points.append(
                {
                    "time": dt.strftime("%H:%M"),
                    "temp": temp,
                }
            )

    forecast_daily = []
    for date_str, info in list(daily.items())[:5]:
        temps = info["temps"]
        forecast_daily.append(
            {
                "date": datetime.fromisoformat(date_str).strftime("%d/%m"),
                "temp_min": round(min(temps), 1),
                "temp_max": round(max(temps), 1),
                "icon": info["icons"][len(info["icons"]) // 2],
                "description": info["descs"][len(info["descs"]) // 2],
            }
        )

    return jsonify(
        {
            "current": current_data,
            "forecast_daily": forecast_daily,
            "hourly": hourly_points,
        }
    )


@app.route("/api/suggest")
def api_suggest():
    """
    Gợi ý tên thành phố (autocomplete).
    """
    query = request.args.get("q")
    if not query:
        return jsonify([])

    params = {
        "q": query,
        "limit": 5,
        "appid": API_KEY,
    }
    try:
        r = requests.get(GEO_URL, params=params)
        data = r.json()
    except Exception:
        return jsonify([])

    suggestions = []
    for item in data:
        name = item["name"]
        country = item.get("country", "")
        state = item.get("state", "")
        label = name
        if state:
            label += f", {state}"
        if country:
            label += f", {country}"
        suggestions.append(
            {
                "name": name,
                "lat": item["lat"],
                "lon": item["lon"],
                "label": label,
            }
        )
    return jsonify(suggestions)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
