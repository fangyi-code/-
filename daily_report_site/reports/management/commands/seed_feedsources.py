from django.core.management.base import BaseCommand

from reports.models import FeedSource

# 默认仅中文 RSS：综合 + 科技/创投（36氪等）；不含英美主流媒体。
DEFAULT_FEEDS = [
    ("新华网时政", "http://www.xinhuanet.com/politics/news_politics.xml"),
    ("人民网时政", "http://www.people.com.cn/rss/politics.xml"),
    ("中新网滚动新闻", "https://www.chinanews.com.cn/rss/scroll-news.xml"),
    ("36氪", "https://36kr.com/feed"),
    ("少数派", "https://sspai.com/feed"),
    ("爱范儿", "https://www.ifanr.com/feed"),
    ("异次元软件世界", "https://feed.iplaysoft.com/"),
]

# 旧版种子中的英文源；用于 --disable-known-en-feeds 关闭已入库条目。
KNOWN_EN_FEED_URLS = (
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.theguardian.com/world/rss",
)


class Command(BaseCommand):
    help = (
        "Insert default Chinese RSS sources if table is empty (or use --force to add missing URLs). "
        "Use --disable-known-en-feeds to turn off legacy BBC/Guardian rows. "
        "After changing feeds, run: python manage.py generate_daily_report"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Add any default feed URLs that are not yet in the database.",
        )
        parser.add_argument(
            "--disable-known-en-feeds",
            action="store_true",
            help="Set enabled=False on FeedSource rows whose URL matches removed English defaults (BBC, Guardian).",
        )

    def handle(self, *args, **options):
        force = options["force"]
        if options["disable_known_en_feeds"]:
            qs = FeedSource.objects.filter(feed_url__in=KNOWN_EN_FEED_URLS, enabled=True)
            n_off = qs.update(enabled=False)
            if n_off:
                self.stdout.write(
                    self.style.WARNING(f"Disabled {n_off} legacy English feed(s).")
                )
            else:
                self.stdout.write("No matching English feeds to disable (or already off).")

        if not FeedSource.objects.exists() or force:
            existing = set(FeedSource.objects.values_list("feed_url", flat=True))
            n = 0
            for name, url in DEFAULT_FEEDS:
                if url in existing:
                    continue
                FeedSource.objects.create(name=name, feed_url=url, enabled=True)
                existing.add(url)
                n += 1
                self.stdout.write(self.style.SUCCESS(f"Added feed: {name}"))
            if n == 0:
                self.stdout.write("No new feeds added.")
        elif not options["disable_known_en_feeds"]:
            self.stdout.write("FeedSource already has rows; use --force to add defaults.")
