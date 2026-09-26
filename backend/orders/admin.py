from django.contrib import admin

from .models import Order, SupplyStatus


@admin.register(SupplyStatus)
class SupplyStatusAdmin(admin.ModelAdmin):
    list_display = ("name", "sort", "is_final")
    list_editable = ("sort", "is_final")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "phone", "full_name", "city", "price", "paid",
                    "remainder_display", "supply_status", "ordered_at")
    list_filter = ("supply_status", "city", "ordered_at")
    search_fields = ("phone", "full_name", "product_title", "external_key", "comment")
    autocomplete_fields = ("user", "product")
    date_hierarchy = "ordered_at"
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Клиент", {"fields": ("user", "phone", "full_name", "city", "delivery_company")}),
        ("Позиция", {"fields": ("product", "product_title")}),
        ("Деньги", {"fields": ("price", "paid")}),
        ("Поставка", {"fields": ("supply_status", "ordered_at", "comment")}),
        ("Служебное", {"fields": ("external_key", "created_at", "updated_at")}),
    )

    @admin.display(description="остаток, ₽")
    def remainder_display(self, obj: Order):
        return obj.remainder
