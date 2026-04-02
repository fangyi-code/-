from django.contrib import admin

from .models import (
    CardComment,
    DailyReport,
    FeedSource,
    NewsItem,
    ReportSection,
    UserProfile,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "city_name", "latitude", "longitude")


@admin.register(FeedSource)
class FeedSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "feed_url", "enabled")
    list_filter = ("enabled",)


class ReportSectionInline(admin.TabularInline):
    model = ReportSection
    extra = 0


class NewsItemInline(admin.TabularInline):
    model = NewsItem
    extra = 0


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ("report_date", "title", "risk_score", "data_collected_at")
    inlines = [ReportSectionInline, NewsItemInline]
    date_hierarchy = "report_date"


@admin.register(CardComment)
class CardCommentAdmin(admin.ModelAdmin):
    list_display = ("news_item", "user", "created_at")
    list_filter = ("created_at",)
