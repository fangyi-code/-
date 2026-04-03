"""Open-Meteo: geocoding + forecast (no API key)."""

from __future__ import annotations

import httpx

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_GEO_COUNT = 20

_FEATURE_RANK: dict[str, int] = {
    "PPLC": 5,
    "PPLA": 4,
    "PPLA2": 3,
    "PPLA3": 3,
    "PPLA4": 3,
}


def _should_try_city_suffix(name: str) -> bool:
    """Append 「市」 for ambiguous short Chinese queries (e.g. 北京 -> 北京市)."""
    if not name or name.endswith("市"):
        return False
    for c in name:
        if c.isascii() and c.isalpha():
            return False
    return True


def _geo_search(name: str) -> list[dict]:
    r = httpx.get(
        GEO_URL,
        params={"name": name, "count": _GEO_COUNT, "language": "zh"},
        timeout=20.0,
    )
    r.raise_for_status()
    return r.json().get("results") or []


def _merge_queries(queries: list[str]) -> list[dict]:
    seen: dict[int, dict] = {}
    for q in queries:
        for row in _geo_search(q.strip()):
            rid = row.get("id")
            if rid is None:
                continue
            if rid not in seen:
                seen[rid] = row
    return list(seen.values())


def _pick_best(results: list[dict]) -> dict | None:
    if not results:
        return None

    def feat_rank(feat: str) -> int:
        return _FEATURE_RANK.get(feat or "", 0)

    def sort_key(r: dict) -> tuple[int, int]:
        return (feat_rank(r.get("feature_code") or ""), int(r.get("population") or 0))

    return max(results, key=sort_key)


def _result_to_label(first: dict, fallback_name: str) -> str:
    label = first.get("name") or fallback_name
    admin = first.get("admin1")
    country = first.get("country")
    parts = [label]
    if admin:
        parts.append(admin)
    if country:
        parts.append(country)
    return ", ".join(parts)


def geocode_city(name: str, count: int = 1) -> tuple[float, float, str] | None:
    """Resolve city name to lat/lon + display label. Picks best match by admin capital / population."""
    del count  # unused; kept for call-site compatibility
    name = (name or "").strip()
    if not name:
        return None
    queries = [name]
    if _should_try_city_suffix(name):
        queries.append(name + "市")
    merged = _merge_queries(queries)
    if not merged:
        return None
    first = _pick_best(merged)
    if not first:
        return None
    lat, lon = float(first["latitude"]), float(first["longitude"])
    label = _result_to_label(first, name)
    return lat, lon, label


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
