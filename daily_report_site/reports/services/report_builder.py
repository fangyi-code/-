"""Assemble daily report: weather + RSS + optional LLM enrichment."""

from __future__ import annotations

from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone

from reports.models import DailyReport, NewsItem, ReportSection
from reports.news_categories import (
    CATEGORY_ORDER,
    LLM_NEWS_CAP,
    PRIMARY_SLUGS,
    full_item_labels_for_persist,
)
from reports.services import llm_client
from reports.services.rss import RawNewsItem
from reports.services import weather as weather_svc


def _default_sections_fallback() -> list[dict[str, Any]]:
    return [
        {
            "slug": "analysis",
            "title": "资讯摘要分析",
            "section_type": "analysis",
            "order": 2,
            "body_markdown": "（模型未配置或调用失败）请根据左侧新闻卡片浏览今日条目。",
        },
        {
            "slug": "risk",
            "title": "风险观察",
            "section_type": "risk",
            "order": 3,
            "body_markdown": "暂无自动评估。",
        },
        {
            "slug": "trend",
            "title": "短期趋势",
            "section_type": "trend",
            "order": 4,
            "body_markdown": "数据不足，请持续积累历史日报后查看「趋势」页。",
        },
        {
            "slug": "scenario",
            "title": "情景推演（课堂练习）",
            "section_type": "scenario",
            "order": 5,
            "body_markdown": "**假设**：关键事件按当前舆情延续。\n\n**可能影响**：市场与情绪短期波动。\n\n**建议**：交叉验证来源，避免单一叙事。",
        },
    ]


def _slug_legend() -> str:
    return "、".join(f"{s}={PRIMARY_SLUGS[s]}" for s in CATEGORY_ORDER)


def build_llm_payload(
    report_date: date,
    place_label: str,
    weather_md: str,
    items: list[RawNewsItem],
    history_snippet: str,
) -> dict[str, Any]:
    lines = []
    n_news = min(len(items), LLM_NEWS_CAP)
    for i, it in enumerate(items[:LLM_NEWS_CAP]):
        lines.append(
            f"{i}. [{it.source_name}] {it.title}\n   摘要: {it.summary[:300]}"
        )
    news_block = "\n".join(lines) if lines else "（无 RSS 条目）"
    system = (
        "你是中文新闻编辑与分析师。只输出一个 JSON 对象，不要 Markdown 代码围栏。"
        " JSON 结构必须严格如下键名："
        '{"ai_summary":"string","risk_score":0-100整数,'
        '"sections":[{"slug":"英文短横线","title":"string","section_type":'
        '"analysis|risk|trend|scenario|news|other之一","order":整数,"body_markdown":"string"}],'
        '"top_story_indices":[0,1,2] 从下面新闻列表中选最多8个下标,'
        '"item_labels":[{"primary":"slug之一","secondary":"短中文或空字符串"}]。'
        f"其中 item_labels 必须为长度 {n_news} 的数组，与新闻列表 0..{max(0, n_news - 1)} 一一对应；"
        f" primary 只能是英文 slug：{','.join(CATEGORY_ORDER)}（含义：{_slug_legend()}）；"
        " secondary 为可选次要标签（≤12 字为宜），无则填\"\"。"
    )
    user = (
        f"报告日期：{report_date.isoformat()}。\n"
        f"地点：{place_label}\n\n"
        f"【天气数据】\n{weather_md}\n\n"
        f"【历史线索（标题词频摘要）】\n{history_snippet}\n\n"
        f"【今日 RSS 新闻列表】（共 {n_news} 条，下标 0 起）\n{news_block}\n\n"
        "要求：sections 至少包含「分析、风险、趋势简述、情景推演」四类语义，可用 section_type 对应 analysis/risk/trend/scenario。"
        " ai_summary 为整报一句话摘要。risk_score 综合舆情与不确定性。"
        " top_story_indices 使用上面编号（须在有效下标范围内）。"
        f" item_labels 必须恰好 {n_news} 个对象，顺序与新闻列表一致。"
    )
    raw = llm_client.chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.35,
    )
    data = llm_client.extract_json_object(raw)
    if not isinstance(data, dict):
        raise ValueError("LLM did not return JSON object")
    return data


@transaction.atomic
def persist_report(
    report_date: date,
    title: str,
    ai_summary: str,
    risk_score: int,
    weather_md: str,
    items: list[RawNewsItem],
    llm_sections: list[dict[str, Any]],
    top_indices: list[int],
    raw_meta: dict,
    per_index_labels: list[dict[str, str]],
) -> DailyReport:
    report, _ = DailyReport.objects.update_or_create(
        report_date=report_date,
        defaults={
            "title": title,
            "ai_summary": ai_summary,
            "data_collected_at": timezone.now(),
            "risk_score": max(0, min(100, int(risk_score))),
            "raw_meta": raw_meta,
        },
    )
    report.sections.all().delete()
    report.news_items.all().delete()

    ReportSection.objects.create(
        report=report,
        slug="weather",
        title="天气与环境",
        order=0,
        section_type=ReportSection.SectionType.WEATHER,
        body_markdown=weather_md,
    )

    order = 1
    used_slugs: set[str] = {"weather"}
    for sec in sorted(llm_sections, key=lambda x: int(x.get("order") or 0)):
        base = (sec.get("slug") or f"sec-{order}").replace(" ", "-")[:120]
        slug = base
        n = 0
        while slug in used_slugs:
            n += 1
            slug = f"{base}-{n}"[:120]
        used_slugs.add(slug)
        st = sec.get("section_type") or "other"
        if st not in dict(ReportSection.SectionType.choices):
            st = ReportSection.SectionType.OTHER
        ReportSection.objects.create(
            report=report,
            slug=slug,
            title=(sec.get("title") or "未命名")[:200],
            order=order,
            section_type=st,
            body_markdown=str(sec.get("body_markdown") or "")[:50000],
        )
        order += 1

    priority: list[int] = []
    for x in top_indices:
        try:
            i = int(x)
            if 0 <= i < len(items) and i not in priority:
                priority.append(i)
        except (TypeError, ValueError):
            continue
    rest = [i for i in range(len(items)) if i not in priority]
    ordered_indices = priority + rest

    for pos, idx in enumerate(ordered_indices):
        it = items[idx]
        imp = float(len(ordered_indices) - pos) / max(len(ordered_indices), 1) * 10
        if pos < len(priority):
            imp = max(imp, 6.0)
        lab = per_index_labels[idx] if idx < len(per_index_labels) else per_index_labels[-1]
        extra = {
            "published": it.published,
            "category_slug": lab["category_slug"],
            "category_label": lab["category_label"],
            "secondary_tag": lab["secondary_tag"],
        }
        NewsItem.objects.create(
            report=report,
            title=it.title,
            url=it.url or "",
            source_name=it.source_name,
            summary=it.summary[:2000],
            importance_score=round(imp, 2),
            order=pos,
            extra=extra,
        )

    return report


def run_build(
    report_date: date,
    city_name: str,
    latitude: float | None,
    longitude: float | None,
    feed_urls: list[str],
    history_snippet: str,
) -> DailyReport:
    from reports.services.rss import fetch_all_feeds

    items = fetch_all_feeds(feed_urls)
    place_label = city_name
    lat, lon = latitude, longitude
    if lat is None or lon is None:
        g = weather_svc.geocode_city(city_name)
        if g:
            lat, lon, place_label = g[0], g[1], g[2]
        else:
            lat, lon, place_label = 39.9, 116.4, "北京（默认）"
    weather_md = weather_svc.weather_markdown(lat, lon, place_label)

    title = f"早报 - {report_date.isoformat()}"

    llm_sections: list[dict[str, Any]] = []
    ai_summary = "今日已聚合 RSS 与天气数据。"
    risk_score = 35
    top_indices: list[int] = list(range(min(8, len(items))))
    raw_meta: dict = {"llm": False, "news_count": len(items)}

    try:
        data = build_llm_payload(
            report_date, place_label, weather_md, items, history_snippet
        )
        ai_summary = str(data.get("ai_summary") or ai_summary)[:5000]
        try:
            risk_score = int(data.get("risk_score", risk_score))
        except (TypeError, ValueError):
            risk_score = 35
        llm_sections = data.get("sections") or []
        if not isinstance(llm_sections, list):
            llm_sections = []
        if not llm_sections:
            llm_sections = _default_sections_fallback()
        top_indices = data.get("top_story_indices") or top_indices
        if not isinstance(top_indices, list):
            top_indices = list(range(min(8, len(items))))
        raw_meta = {"llm": True, "news_count": len(items), "raw_response": data}
        per_index_labels = full_item_labels_for_persist(len(items), data.get("item_labels"))
    except Exception as exc:
        llm_sections = _default_sections_fallback()
        raw_meta = {
            "llm": False,
            "error": str(exc)[:500],
            "news_count": len(items),
        }
        per_index_labels = full_item_labels_for_persist(len(items), None)

    return persist_report(
        report_date=report_date,
        title=title,
        ai_summary=ai_summary,
        risk_score=risk_score,
        weather_md=weather_md,
        items=items,
        llm_sections=llm_sections,
        top_indices=top_indices,
        raw_meta=raw_meta,
        per_index_labels=per_index_labels,
    )
