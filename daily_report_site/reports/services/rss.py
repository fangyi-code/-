"""Fetch normalized items from RSS/Atom feeds."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import urlparse

import feedparser
import httpx


@dataclass
class RawNewsItem:
    title: str
    url: str
    source_name: str
    published: str | None
    summary: str


def _source_name_from_feed(feed_url: str, feed: dict) -> str:
    title = (feed.get("feed") or {}).get("title") or ""
    if title:
        return title.strip()[:200]
    host = urlparse(feed_url).netloc or "RSS"
    return host[:200]


def _entry_summary(entry: dict) -> str:
    if entry.get("summary"):
        return str(entry["summary"])[:2000]
    if entry.get("description"):
        return str(entry["description"])[:2000]
    return ""


def _entry_published(entry: dict) -> str | None:
    for key in ("published", "updated"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt:
                return dt.isoformat()
        except (TypeError, ValueError):
            pass
        return str(raw)[:80]
    return None


def fetch_feed(feed_url: str, timeout: float = 25.0) -> list[RawNewsItem]:
    """Parse feed from URL (HTTP fetch + feedparser)."""
    headers = {
        "User-Agent": "DailyReportBot/1.0 (+classroom project; RSS)",
    }
    r = httpx.get(feed_url, headers=headers, timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    parsed = feedparser.parse(r.content)
    source = _source_name_from_feed(feed_url, parsed)
    out: list[RawNewsItem] = []
    for entry in (parsed.entries or [])[:40]:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title:
            continue
        if not link:
            link = f"urn:hash:{hashlib.sha256(title.encode()).hexdigest()[:16]}"
        out.append(
            RawNewsItem(
                title=title[:500],
                url=link[:800],
                source_name=source,
                published=_entry_published(entry),
                summary=_entry_summary(entry),
            )
        )
    return out


def fetch_all_feeds(urls: Iterable[str]) -> list[RawNewsItem]:
    seen: set[str] = set()
    merged: list[RawNewsItem] = []
    for u in urls:
        u = (u or "").strip()
        if not u:
            continue
        try:
            items = fetch_feed(u)
        except Exception:
            continue
        for it in items:
            key = it.url or it.title
            if key in seen:
                continue
            seen.add(key)
            merged.append(it)
    return merged[:80]
