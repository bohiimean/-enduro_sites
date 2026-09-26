from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import PhoneNumber, User


class PhoneNumberInline(admin.TabularInline):
    model = PhoneNumber
    extra = 0
    fields = ("phone", "verified_at", "verification_method", "created_at")
    readonly_fields = ("created_at",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-created_at"]
    list_display = ("phone", "full_name", "verified_phone", "is_staff", "is_active", "created_at")
    list_filter = ("is_staff", "is_active")
    search_fields = ("phone", "full_name", "email")
    readonly_fields = ("created_at", "last_login")
    inlines = [PhoneNumberInline]
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Профиль", {"fields": ("full_name", "email")}),
        ("Права", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Служебное", {"fields": ("last_login", "created_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "password1", "password2")}),
    )

    @admin.display(description="номер подтверждён", boolean=True)
    def verified_phone(self, obj: User) -> bool:
        return obj.has_verified_phone


@admin.register(PhoneNumber)
class PhoneNumberAdmin(admin.ModelAdmin):
    list_display = ("phone", "user", "verified_at", "verification_method", "created_at")
    list_filter = ("verification_method", ("verified_at", admin.EmptyFieldListFilter))
    search_fields = ("phone", "user__phone", "user__full_name")
    autocomplete_fields = ("user",)
