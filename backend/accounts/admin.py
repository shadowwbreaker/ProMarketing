from django.contrib import admin

from .models import Role, User, UserProfile, UserRole, UserSanction


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "status", "is_email_verified", "is_staff", "date_joined"]
    search_fields = ["email"]
    exclude = ["password"]


admin.site.register([UserProfile, Role, UserRole, UserSanction])
