from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    city_name = models.CharField(max_length=120, default="北京")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    dark_mode_preference = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} · {self.city_name}"


class FeedSource(models.Model):
    name = models.CharField(max_length=200)
    feed_url = models.URLField(max_length=500)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DailyReport(models.Model):
    report_date = models.DateField(unique=True, db_index=True)
    title = models.CharField(max_length=300)
    ai_summary = models.TextField(blank=True)
    data_collected_at = models.DateTimeField(default=timezone.now)
    risk_score = models.PositiveSmallIntegerField(
        default=30,
        help_text="0-100，风险评估",
    )
    raw_meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-report_date"]

    def __str__(self):
        return f"{self.report_date} {self.title}"


class ReportSection(models.Model):
    class SectionType(models.TextChoices):
        WEATHER = "weather", "天气"
        NEWS = "news", "新闻"
        ANALYSIS = "analysis", "分析"
        RISK = "risk", "风险"
        TREND = "trend", "趋势"
        SCENARIO = "scenario", "情景推演"
        OTHER = "other", "其他"

    report = models.ForeignKey(
        DailyReport,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    slug = models.SlugField(max_length=120)
    title = models.CharField(max_length=200)
    order = models.PositiveSmallIntegerField(default=0)
    section_type = models.CharField(
        max_length=32,
        choices=SectionType.choices,
        default=SectionType.OTHER,
    )
    body_markdown = models.TextField(blank=True)

    class Meta:
        ordering = ["report", "order", "id"]
        unique_together = [["report", "slug"]]

    def __str__(self):
        return f"{self.report.report_date} · {self.title}"


class NewsItem(models.Model):
    report = models.ForeignKey(
        DailyReport,
        on_delete=models.CASCADE,
        related_name="news_items",
    )
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=800, blank=True)
    source_name = models.CharField(max_length=200, blank=True)
    summary = models.TextField(blank=True)
    importance_score = models.FloatField(null=True, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["report", "order", "-importance_score", "id"]

    def __str__(self):
        return self.title[:80]


class CardComment(models.Model):
    news_item = models.ForeignKey(
        NewsItem,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="card_comments",
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user_id} on {self.news_item_id}"
