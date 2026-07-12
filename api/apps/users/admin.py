from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.users.models import SocialAccount, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["id", "username", "nickname", "email", "is_active", "date_joined"]
    search_fields = ["username", "nickname", "email"]
    fieldsets = UserAdmin.fieldsets + (("프로필", {"fields": ("nickname", "profile_image")}),)


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "provider", "provider_user_id", "email", "connected_at"]
    list_filter = ["provider"]
    search_fields = ["provider_user_id", "email", "user__nickname"]
