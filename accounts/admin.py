from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = [
    "email",
    "username",
    "is_staff",
    "print_jobs_limit",
    "role",
    ]
    fieldsets = UserAdmin.fieldsets + (
        (None, {"fields": ("role", "print_jobs_limit","must_change_password",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {"fields": ("role", "print_jobs_limit","must_change_password",)}),
    )
admin.site.register(CustomUser, CustomUserAdmin)
