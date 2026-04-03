"""Primary news category slugs for LLM classification and UI grouping."""

from __future__ import annotations

from typing import Any

# Ordered slug -> 中文标题（目录与正文分块标题）
PRIMARY_SLUGS: dict[str, str] = {
    "intl": "国际局势",
    "business": "商业与经济",
    "society": "社会民生",
    "tech": "科技与创新",
    "other": "其他",
}

# 稳定遍历顺序（「其他」放最后）
CATEGORY_ORDER: tuple[str, ...] = ("intl", "business", "society", "tech", "other")

# 与 LLM 新闻列表条数上限一致
LLM_NEWS_CAP = 60

SECONDARY_TAG_MAX_LEN = 24


def normalize_primary_slug(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in PRIMARY_SLUGS:
        return s
    return "other"


def label_for_slug(slug: str) -> str:
    return PRIMARY_SLUGS.get(slug, PRIMARY_SLUGS["other"])


def default_label_row() -> dict[str, str]:
    return {
        "category_slug": "other",
        "category_label": label_for_slug("other"),
        "secondary_tag": "",
    }


def normalize_item_labels_from_llm(raw: Any, count: int) -> list[dict[str, str]]:
    """
    Parse LLM `item_labels` into `count` rows aligned with news list indices 0..count-1.
    Each row: category_slug, category_label, secondary_tag.
    """
    rows: list[dict[str, str]] = []
    raw_list = raw if isinstance(raw, list) else []
    for i in range(count):
        slug = "other"
        sec = ""
        if i < len(raw_list):
            row = raw_list[i]
            if isinstance(row, dict):
                slug = normalize_primary_slug(row.get("primary"))
                sec = str(row.get("secondary") or "").strip()
            elif isinstance(row, (list, tuple)) and len(row) >= 1:
                slug = normalize_primary_slug(row[0])
                sec = str(row[1]).strip() if len(row) > 1 else ""
        sec = sec[:SECONDARY_TAG_MAX_LEN]
        rows.append(
            {
                "category_slug": slug,
                "category_label": label_for_slug(slug),
                "secondary_tag": sec,
            }
        )
    return rows


def full_item_labels_for_persist(items_len: int, llm_item_labels: Any | None) -> list[dict[str, str]]:
    """Length items_len; first min(items_len, LLM_NEWS_CAP) from LLM (non-list treated as empty), rest other."""
    n = min(items_len, LLM_NEWS_CAP)
    base = normalize_item_labels_from_llm(llm_item_labels, n)
    other = default_label_row()
    out: list[dict[str, str]] = []
    for i in range(items_len):
        if i < len(base):
            out.append(base[i])
        else:
            out.append(dict(other))
    return out
