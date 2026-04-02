"""Trim old DailyReport rows to bound database size (cascades sections, news, comments)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.utils import timezone

from reports.models import DailyReport

RETENTION_DAYS = 30


def prune_old_daily_reports(
    *,
    days: int = RETENTION_DAYS,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Remove DailyReport with report_date strictly before (local today - days).

    Returns a dict with cutoff date, number of DailyReport rows affected, and either
    report_dates (dry_run) or deleted_total (actual delete).
    """
    cutoff: date = timezone.localdate() - timedelta(days=days)
    qs = DailyReport.objects.filter(report_date__lt=cutoff).order_by("report_date")
    report_count = qs.count()
    if dry_run:
        return {
            "cutoff": cutoff,
            "days": days,
            "report_count": report_count,
            "report_dates": list(qs.values_list("report_date", flat=True)),
        }
    if report_count == 0:
        return {
            "cutoff": cutoff,
            "days": days,
            "report_count": 0,
            "deleted_total": 0,
        }
    deleted_total, _by_model = qs.delete()
    return {
        "cutoff": cutoff,
        "days": days,
        "report_count": report_count,
        "deleted_total": deleted_total,
    }
