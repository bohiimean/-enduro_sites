from decimal import Decimal

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html_join

from .models import Brand, CatalogSettings, Product, ProductPhoto, ProductSpec
from .pricing import CatalogRate, current_rate, offers


def rub(value: Decimal | None) -> str:
    if value is None:
        return "по запросу"
    return f"{value:,.0f} ₽".replace(",", " ")


def rate_line(rate: CatalogRate | None) -> str:
    if rate is None:
        return "Курса нет — цены от юаней не считаются, на сайте «по запросу»"
    at = timezone.localtime(rate.fetched_at)
    return f"Цена юаня {rate.price_per_cny} ₽, курс от {at:%d.%m %H:%M}"


class ProductPhotoInline(admin.TabularInline):
    model = ProductPhoto
    extra = 1
    fields = ("image", "sort")


class ProductSpecInline(admin.TabularInline):
    model = ProductSpec
    extra = 1
    fields = ("name", "value", "sort")
    verbose_name_plural = "дополнительные характеристики (реверс, рекуперация, режимы…)"


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort", "is_active", "products_count")
    list_editable = ("sort", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="байков")
    def products_count(self, obj: Brand) -> int:
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "powertrain", "price_cny", "stock_qty", "stock_price_rub",
                    "is_orderable", "is_published", "sort", "updated_at")
    list_filter = ("brand", "powertrain", "is_orderable", "is_published")
    list_editable = ("stock_qty", "is_orderable", "is_published", "sort")
    search_fields = ("model", "brand__name")
    autocomplete_fields = ("brand",)
    readonly_fields = ("site_prices", "created_at", "updated_at")
    inlines = [ProductPhotoInline, ProductSpecInline]
    fieldsets = (
        (None, {"fields": (
            "brand", "model", "model_year", "powertrain", "tagline", "description",
            "colors", "documents",
        )}),
        ("Цена и наличие", {"fields": (
            "price_cny", "delivery_rub", "stock_qty", "stock_price_rub",
            "is_orderable", "lead_time", "site_prices",
        )}),
        ("Характеристики", {"fields": (
            "engine", ("power_hp", "power_kw"), "torque_nm", "max_speed_kmh",
            "weight_kg", "seat_height_mm", "ground_clearance_mm",
            "frame", "fork", "shock", "brakes", "wheels",
        )}),
        ("Только ДВС", {"fields": (
            "displacement_cc", "cooling", "fuel_system", "transmission", "starter", "fuel_tank_l",
        )}),
        ("Только электро", {"fields": (
            "battery_voltage_v", "battery_capacity_ah", "range_km", "charge_time_h",
        )}),
        ("Публикация", {"fields": ("is_published", "sort", "slug", "created_at", "updated_at")}),
    )

    @admin.display(description="цены на сайте сейчас")
    def site_prices(self, obj: Product):
        if obj.pk is None:
            return "Появятся после сохранения."
        config = CatalogSettings.load()
        found = offers(obj, config, current_rate(config))
        lines = [
            f"В наличии, {found.stock.qty} шт: {rub(found.stock.price_rub)}"
            if found.stock else "В наличии: нет",
            f"Под заказ: {rub(found.order.price_rub)}" if found.order else "Предзаказ выключен",
            rate_line(found.rate),
        ]
        return format_html_join("", "<div>{}</div>", ((line,) for line in lines))


@admin.register(CatalogSettings)
class CatalogSettingsAdmin(admin.ModelAdmin):
    list_display = ("__str__", "rate_method", "order_markup_percent", "stock_markup_percent",
                    "delivery_rub", "round_to_rub", "updated_at")
    readonly_fields = ("rate_now",)

    def has_add_permission(self, request):
        return not CatalogSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="курс сейчас")
    def rate_now(self, obj: CatalogSettings) -> str:
        return rate_line(current_rate(obj))
