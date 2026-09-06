from flask import Flask, render_template, request, jsonify
import requests
import math

app = Flask(__name__)

# Open-Meteo APIs (Free & No API Key Required)
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

def get_risk_level(hi_value):
    """Categorizes heat index into threat levels and map colors."""
    if hi_value < 27:
        return {"level": "Low", "color": "#10b981", "bg_class": "emerald"}
    elif 27 <= hi_value < 32:
        return {"level": "Caution", "color": "#f59e0b", "bg_class": "amber"}
    elif 32 <= hi_value < 41:
        return {"level": "High Risk", "color": "#f97316", "bg_class": "orange"}
    else:
        return {"level": "Extreme Crisis", "color": "#ef4444", "bg_class": "red"}

def calculate_apparent_temp(temp, humidity, wind_kmh):
    """Calculates apparent temperature (Heat Index) native formula."""
    e = (humidity / 100.0) * 6.105 * math.exp((17.27 * temp) / (237.7 + temp))
    wind_ms = wind_kmh / 3.6 
    return round(temp + 0.33 * e - 0.70 * wind_ms - 4.0, 1)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/get_heat_data", methods=["GET"])
def get_heat_data():
    city = request.args.get("city", "Delhi")

    try:
        # 1. Geocoding API Step
        geo_res = requests.get(GEOCODING_URL, params={"name": city, "count": 1, "language": "en", "format": "json"}).json()
        
        if not geo_res.get("results"):
            return jsonify({"error": f"City '{city}' not found."}), 404

        loc = geo_res["results"][0]
        lat = loc["latitude"]
        lon = loc["longitude"]
        city_name = loc.get("name", city)
        country = loc.get("country", "")

        # 2. Open-Meteo Weather API Step (Includes hourly params for Chart.js)
        weather_params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
            "daily": "temperature_2m_max",
            "forecast_days": 5,
            "timezone": "auto"
        }
        w_res = requests.get(WEATHER_URL, params=weather_params).json()
        
        # Current Metrics
        current_data = w_res.get("current", {})
        temp = current_data.get("temperature_2m", 30.0)
        humidity = current_data.get("relative_humidity_2m", 50.0)
        wind_kmh = current_data.get("wind_speed_10m", 10.0)
        apparent_temp = calculate_apparent_temp(temp, humidity, wind_kmh)

        # 3. 24-Hour Graph Data Processing
        hourly_raw = w_res.get("hourly", {})
        times = [t.split("T")[1] for t in hourly_raw.get("time", [])[:24]]
        temps = hourly_raw.get("temperature_2m", [])[:24]
        humidities = hourly_raw.get("relative_humidity_2m", [])[:24]
        winds = hourly_raw.get("wind_speed_10m", [])[:24]

        apparent_temps = [
            calculate_apparent_temp(t, h, w) 
            for t, h, w in zip(temps, humidities, winds)
        ]

        # 4. Determine Threat Risk & Color Code
        risk = get_risk_level(apparent_temp)
        daily_forecast = w_res.get("daily", {}).get("temperature_2m_max", [])

        return jsonify({
            "status": "success",
            "city": f"{city_name}, {country}",
            "lat": lat,
            "lng": lon,
            "temp": round(temp, 1),
            "humidity": round(humidity, 1),
            "wind": round(wind_kmh, 1),
            "apparent_temp": apparent_temp,
            "risk": risk["level"],
            "color": risk["color"],
            "forecast": daily_forecast,
            "graph_data": {
                "labels": times,
                "ambient": temps,
                "apparent": apparent_temps
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)