from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from reports.models import FeedSource, NewsItem
from reports.services.report_builder import run_build
from reports.services.retention import prune_old_daily_reports


def build_history_snippet(days: int = 7, max_lines: int = 30) -> str:
    since = timezone.localdate() - timedelta(days=days)
    titles = list(
        NewsItem.objects.filter(report__report_date__gte=since)
        .values_list("title", flat=True)[:500]
    )
    if not titles:
        return "（尚无历史新闻标题）"
    bigrams: Counter[str] = Counter()
    for t in titles:
        s = "".join(t.split())
        for i in range(len(s) - 1):
            bigrams[s[i : i + 2]] += 1
    common = [f"{k}({v})" for k, v in bigrams.most_common(25)]
    return "高频二字片段（示意）：" + "，".join(common[:max_lines])


class Command(BaseCommand):
    help = "Fetch RSS + weather, call LLM (if configured), upsert today's DailyReport."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default="",
            help="Report date YYYY-MM-DD (default: today in Asia/Shanghai).",
        )

    def handle(self, *args, **options):
        from django.core.management import call_command

        if not FeedSource.objects.filter(enabled=True).exists():
            call_command("seed_feedsources")

        tz = timezone.get_current_timezone()
        if options["date"]:
            from datetime import datetime

            report_date = datetime.strptime(options["date"], "%Y-%m-%d").date()
        else:
            report_date = timezone.localdate()

        urls = list(
            FeedSource.objects.filter(enabled=True).values_list("feed_url", flat=True)
        )
        city = settings.DEFAULT_CITY_NAME
        lat = lon = None
        history = build_history_snippet()
        r = run_build(
            report_date=report_date,
            city_name=city,
            latitude=lat,
            longitude=lon,
            feed_urls=urls,
            history_snippet=history,
        )
        self.stdout.write(self.style.SUCCESS(f"OK: {r} ({r.news_items.count()} news)"))
        pr = prune_old_daily_reports()
        if pr["report_count"] == 0:
            self.stdout.write("Retention: no old reports to prune.")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Retention: pruned {pr['report_count']} report(s) older than "
                    f"{pr['cutoff']} ({pr['deleted_total']} objects incl. cascades)."
                )
            )
