"""Open-Meteo: geocoding + forecast (no API key)."""

from __future__ import annotations

import httpx

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def geocode_city(name: str, count: int = 1) -> tuple[float, float, str] | None:
    name = (name or "").strip()
    if not name:
        return None
    r = httpx.get(
        GEO_URL,
        params={"name": name, "count": count, "language": "zh"},
        timeout=20.0,
    )
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    if not results:
        return None
    first = results[0]
    lat, lon = float(first["latitude"]), float(first["longitude"])
    label = first.get("name") or name
    admin = first.get("admin1")
    country = first.get("country")
    parts = [label]
    if admin:
        parts.append(admin)
    if country:
        parts.append(country)
    return lat, lon, ", ".join(parts)


def fetch_forecast(lat: float, lon: float) -> dict:
    r = httpx.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "weather_code",
                "wind_speed_10m",
            ],
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "weather_code",
            ],
            "timezone": "Asia/Shanghai",
            "forecast_days": 2,
        },
        timeout=25.0,
    )
    r.raise_for_status()
    return r.json()


def weather_markdown(lat: float, lon: float, place_label: str) -> str:
    fc = fetch_forecast(lat, lon)
    cur = fc.get("current") or {}
    daily = fc.get("daily") or {}
    t = cur.get("temperature_2m")
    ap = cur.get("apparent_temperature")
    rh = cur.get("relative_humidity_2m")
    wcode = cur.get("weather_code")
    wind = cur.get("wind_speed_10m")
    lines = [
        f"**地点**：{place_label}（{lat:.2f}, {lon:.2f}）",
        f"**当前气温**：{t} °C（体感 {ap} °C）" if t is not None else "",
        f"**湿度**：{rh} %" if rh is not None else "",
        f"**风速**：{wind} km/h" if wind is not None else "",
        f"**天气代码（WMO）**：{wcode}" if wcode is not None else "",
    ]
    tmax = (daily.get("temperature_2m_max") or [None])[0]
    tmin = (daily.get("temperature_2m_min") or [None])[0]
    if tmax is not None and tmin is not None:
        lines.append(f"**今日预报**：最高 {tmax} °C / 最低 {tmin} °C")
    tmax2 = (daily.get("temperature_2m_max") or [None, None])[1]
    tmin2 = (daily.get("temperature_2m_min") or [None, None])[1]
    if tmax2 is not None and tmin2 is not None:
        lines.append(f"**明日**：最高 {tmax2} °C / 最低 {tmin2} °C")
    return "\n\n".join(x for x in lines if x)
