from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.today, name="today"),
    path("report/<str:day>/", views.report_day, name="report_day"),
    path("history/", views.history, name="history"),
    path("trends/", views.trends, name="trends"),
    path("app-settings/", views.app_settings, name="app_settings"),
    path("accounts/register/", views.register, name="register"),
    path(
        "accounts/login/",
        LoginView.as_view(template_name="reports/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        LogoutView.as_view(next_page="/"),
        name="logout",
    ),
    path("news/<int:pk>/comment/", views.comment_add, name="comment_add"),
    path("api/search/", views.api_search, name="api_search"),
    path("api/feeds/", views.feeds_json, name="feeds_json"),
]
