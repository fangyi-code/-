from __future__ import annotations

import re
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CardCommentForm, RegisterForm, UserProfileForm
from .models import CardComment, DailyReport, FeedSource, NewsItem, UserProfile
from .services import llm_client


def _ensure_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"city_name": settings.DEFAULT_CITY_NAME},
    )
    return profile


def _report_context(request, report: DailyReport):
    sections = list(report.sections.all())
    news = list(
        report.news_items.annotate(comments_count=Count("comments"))
        .prefetch_related("comments")
        .order_by("order", "-importance_score", "id")[:60]
    )
    comment_count = CardComment.objects.filter(news_item__report=report).count()
    news_count = report.news_items.count()
    risk = int(report.risk_score or 0)
    toc = [{"slug": s.slug, "title": s.title, "type": s.section_type} for s in sections]
    for n in news[:12]:
        toc.append(
            {
                "slug": f"news-{n.id}",
                "title": n.title[:40] + ("…" if len(n.title) > 40 else ""),
                "type": "news",
            }
        )
    return {
        "report": report,
        "sections": sections,
        "news_items": news,
        "comment_count": comment_count,
        "news_count": news_count,
        "risk_score": risk,
        "toc": toc,
    }


def today(request):
    report = DailyReport.objects.order_by("-report_date").first()
    if not report:
        return render(
            request,
            "reports/empty.html",
            {
                "tab": "today",
                "message": "尚无日报。请在项目目录执行：python manage.py generate_daily_report",
            },
        )
    ctx = _report_context(request, report)
    ctx["tab"] = "today"
    ctx["feeds"] = FeedSource.objects.filter(enabled=True)
    if request.user.is_authenticated:
        ctx["profile"] = _ensure_profile(request.user)
    return render(request, "reports/today.html", ctx)


def report_day(request, day: str):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", day):
        return redirect("today")
    report = get_object_or_404(DailyReport, report_date=day)
    ctx = _report_context(request, report)
    ctx["tab"] = "history"
    ctx["feeds"] = FeedSource.objects.filter(enabled=True)
    if request.user.is_authenticated:
        ctx["profile"] = _ensure_profile(request.user)
    return render(request, "reports/today.html", ctx)


def history(request):
    items = DailyReport.objects.order_by("-report_date")[:120]
    return render(request, "reports/history.html", {"reports": items, "tab": "history"})


def trends(request):
    since = timezone.localdate() - timedelta(days=30)
    titles = list(
        NewsItem.objects.filter(report__report_date__gte=since).values_list(
            "title", flat=True
        )[:800]
    )
    bigrams: Counter[str] = Counter()
    for t in titles:
        s = "".join(str(t).split())
        for i in range(max(0, len(s) - 1)):
            bigrams[s[i : i + 2]] += 1
    top = bigrams.most_common(40)
    by_day = (
        DailyReport.objects.filter(report_date__gte=since)
        .annotate(n=Count("news_items"))
        .order_by("report_date")
        .values("report_date", "n", "risk_score")
    )
    return render(
        request,
        "reports/trends.html",
        {
            "tab": "trends",
            "top_bigrams": top,
            "by_day": list(by_day),
        },
    )


@login_required
def app_settings(request):
    profile = _ensure_profile(request.user)
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "已保存设置。")
            return redirect("app_settings")
    else:
        form = UserProfileForm(instance=profile)
    feeds = FeedSource.objects.all()
    return render(
        request,
        "reports/settings.html",
        {"tab": "settings", "form": form, "feeds": feeds},
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("today")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(
                user=user, city_name=settings.DEFAULT_CITY_NAME
            )
            login(request, user)
            messages.success(request, "注册成功。")
            return redirect("today")
    else:
        form = RegisterForm()
    return render(request, "reports/register.html", {"form": form})


@require_POST
@login_required
def comment_add(request, pk: int):
    news = get_object_or_404(NewsItem, pk=pk)
    form = CardCommentForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.user = request.user
        c.news_item = news
        c.save()
        messages.success(request, "评论已发布。")
    else:
        messages.error(request, "评论无效或过长。")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_POST
def api_search(request):
    q = (request.POST.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"ok": False, "error": "至少输入 2 个字符"}, status=400)
    since = timezone.localdate() - timedelta(days=120)
    reports = DailyReport.objects.filter(report_date__gte=since).order_by("-report_date")[
        :25
    ]
    chunks = []
    for r in reports:
        parts = [f"DATE {r.report_date}", r.title, r.ai_summary[:800]]
        for s in r.sections.all()[:12]:
            parts.append(f"#{s.slug} {s.title}: {s.body_markdown[:400]}")
        for n in r.news_items.all()[:15]:
            parts.append(f"NEWS {n.title}: {n.summary[:200]}")
        chunks.append("\n".join(parts)[:6000])
    blob = "\n---\n".join(chunks)[:25000]
    prompt = (
        f"用户问题：{q}\n\n下面是多份日报拼接片段，请判断最相关的日期与章节锚点。"
        ' 只输出 JSON：{{"report_date":"YYYY-MM-DD或null","anchor_slug":"英文slug或news-数字id或null",'
        '"answer":"中文简短回答，说明定位依据"}}'
    )
    try:
        raw = llm_client.chat_completion(
            [
                {"role": "system", "content": "你是检索助手，只输出 JSON。"},
                {"role": "user", "content": prompt + "\n\n---\n" + blob},
            ],
            temperature=0.2,
        )
        data = llm_client.extract_json_object(raw) or {}
    except Exception as exc:
        data = {
            "report_date": None,
            "anchor_slug": None,
            "answer": f"（搜索服务不可用：{exc}）请改用历史列表浏览。",
        }
    return JsonResponse({"ok": True, **data})


def feeds_json(request):
    data = list(FeedSource.objects.values("name", "feed_url", "enabled"))
    return JsonResponse({"feeds": data})
