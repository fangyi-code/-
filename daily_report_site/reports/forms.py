from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import CardComment, UserProfile


class RegisterForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("city_name", "latitude", "longitude", "dark_mode_preference")
        labels = {
            "city_name": "默认城市",
            "latitude": "纬度（可选）",
            "longitude": "经度（可选）",
            "dark_mode_preference": "偏好深色（可与页顶开关同步）",
        }


class CardCommentForm(forms.ModelForm):
    class Meta:
        model = CardComment
        fields = ("body",)
        labels = {"body": "评论"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].widget.attrs.update(
            {"rows": 2, "placeholder": "登录后发表评论…"}
        )
