"""Client IP and coarse geo for weather (server-side HTTP only)."""

from __future__ import annotations

import ipaddress
from urllib.parse import quote

import httpx
from django.conf import settings

IP_API_FIELDS = "status,message,lat,lon,city,regionName,countryCode"


def get_client_ip(request) -> str:
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        xff = request.META.get("HTTP_X_FORWARDED_FOR") or ""
        if xff.strip():
            return xff.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def _is_public_routable(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.is_loopback or addr.is_link_local or addr.is_reserved:
        return False
    if addr.is_private or addr.is_multicast:
        return False
    return True


def ip_to_lat_lon_label(ip: str) -> tuple[float, float, str] | None:
    """
    Return (lat, lon, place_label) from ip-api.com for a public IP, or None.
    Local/private/loopback IPs return None (caller falls back to default city).
    """
    if not ip or not _is_public_routable(ip):
        return None
    try:
        r = httpx.get(
            f"http://ip-api.com/json/{quote(ip, safe='')}",
            params={"fields": IP_API_FIELDS},
            timeout=5.0,
        )
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return None
    if data.get("status") != "success":
        return None
    try:
        lat = float(data["lat"])
        lon = float(data["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    city = (data.get("city") or "").strip()
    region = (data.get("regionName") or "").strip()
    cc = (data.get("countryCode") or "").strip()
    parts = [p for p in (city, region, cc) if p]
    label = ", ".join(parts) if parts else "IP 定位"
    return lat, lon, label
