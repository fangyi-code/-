from django.core.management.base import BaseCommand

from reports.services.retention import RETENTION_DAYS, prune_old_daily_reports


class Command(BaseCommand):
    help = (
        f"Delete DailyReport older than {RETENTION_DAYS} days by default "
        "(cascades sections, news items, comments). Use --dry-run to preview."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=RETENTION_DAYS,
            help=f"Keep reports on or after (today - days). Default: {RETENTION_DAYS}.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List report_date that would be removed; do not delete.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry = options["dry_run"]
        result = prune_old_daily_reports(days=days, dry_run=dry)
        cutoff = result["cutoff"]
        n = result["report_count"]
        self.stdout.write(f"Retention: keep report_date >= {cutoff} (days={days}).")
        if dry:
            dates = result["report_dates"]
            if not dates:
                self.stdout.write(self.style.SUCCESS("Dry-run: nothing to delete."))
                return
            self.stdout.write(
                self.style.WARNING(
                    f"Dry-run: would delete {n} DailyReport(s): {', '.join(str(d) for d in dates)}"
                )
            )
            return
        if n == 0:
            self.stdout.write(self.style.SUCCESS("Prune: no old reports to delete."))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Prune: removed {n} DailyReport(s); {result['deleted_total']} object(s) total (with cascades)."
            )
        )
