from decimal import Decimal

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from .models import (
    Brand, CatalogSettings, Goods, GoodsCategory, GoodsPhoto, GoodsSpec,
    Product, ProductPhoto, ProductSpec,
)
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


def photo_preview(image):
    if not image:
        return "—"
    return format_html(
        '<img src="{}" alt="Фото товара" width="80" height="60" loading="lazy" '
        'style="object-fit:contain;border-radius:6px;background:#f3f4f6">', image.url,
    )


class StockFilter(admin.SimpleListFilter):
    title = "наличие"
    parameter_name = "availability"

    def lookups(self, request, model_admin):
        return [("stock", "В наличии"), ("order", "Под заказ")]

    def queryset(self, request, queryset):
        if self.value() == "stock":
            return queryset.filter(stock_qty__gt=0)
        if self.value() == "order":
            return queryset.filter(is_orderable=True)
        return queryset


class PhotoPreviewMixin:
    @admin.display(description="фото")
    def thumbnail(self, obj):
        photo = next(iter(obj.photos.all()), None)
        return photo_preview(photo.image) if photo else "—"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("photos")


class ProductPhotoInline(TabularInline):
    model = ProductPhoto
    extra = 1
    tab = True
    ordering_field = "sort"
    template_before = "admin/catalog/ordering_hint.html"
    hide_ordering_field = True
    fields = ("preview", "image", "sort")
    readonly_fields = ("preview",)

    @admin.display(description="фото")
    def preview(self, obj):
        return photo_preview(obj.image)


class ProductSpecInline(TabularInline):
    model = ProductSpec
    extra = 1
    tab = True
    ordering_field = "sort"
    template_before = "admin/catalog/ordering_hint.html"
    hide_ordering_field = True
    fields = ("name", "value", "sort")
    verbose_name_plural = "доп. характеристики"


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    list_display = ("name", "slug", "sort", "is_active", "products_count")
    list_editable = ("sort", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="байков")
    def products_count(self, obj: Brand) -> int:
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(PhotoPreviewMixin, ModelAdmin):
    list_filter_submit = True
    list_fullwidth = True
    compressed_fields = True
    list_display = ("thumbnail", "title", "powertrain", "price_cny", "stock_qty", "stock_price_rub",
                    "is_orderable", "is_published", "sort", "updated_at")
    list_filter = ("is_published", StockFilter, "brand", "powertrain")
    list_display_links = ("thumbnail", "title")
    list_editable = ("stock_qty", "is_orderable", "is_published", "sort")
    search_fields = ("model", "brand__name")
    autocomplete_fields = ("brand",)
    readonly_fields = ("site_prices", "created_at", "updated_at")
    inlines = [ProductPhotoInline, ProductSpecInline]
    fieldsets = (
        ("Основное", {"classes": ("tab",), "fields": (
            "brand", "model", "model_year", "powertrain", "tagline", "description",
            "colors", "documents",
        )}),
        ("Цена и наличие", {"classes": ("tab",), "fields": (
            "price_cny", "delivery_rub", "stock_qty", "stock_price_rub",
            "is_orderable", "lead_time", "site_prices",
        )}),
        ("Характеристики", {"classes": ("tab",), "fields": (
            "engine", ("power_hp", "power_kw"), "torque_nm", "max_speed_kmh",
            "weight_kg", "seat_height_mm", "ground_clearance_mm",
            "frame", "fork", "shock", "brakes", "wheels",
        )}),
        ("Двигатель и батарея", {"classes": ("tab",), "description": "Поля зависят от типа байка. Заполненные поля другого типа остаются видимыми: очистите их перед сохранением.", "fields": (
            "displacement_cc", "cooling", "fuel_system", "transmission", "starter", "fuel_tank_l",
            "battery_voltage_v", "battery_capacity_ah", "range_km", "charge_time_h",
        )}),
        ("Публикация", {"classes": ("tab",), "fields": ("is_published", "sort", "slug", "created_at", "updated_at")}),
    )

    conditional_fields = {
        **{name: f"powertrain !== 'electric' || ({name} !== '' && {name} != null)" for name in Product.ICE_ONLY},
        **{name: f"powertrain === 'electric' || ({name} !== '' && {name} != null)" for name in Product.ELECTRIC_ONLY},
    }

    def view_on_site(self, obj):
        return f"/catalog/{obj.slug}"

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
class CatalogSettingsAdmin(ModelAdmin):
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


class GoodsPhotoInline(TabularInline):
    model = GoodsPhoto
    extra = 1
    tab = True
    ordering_field = "sort"
    template_before = "admin/catalog/ordering_hint.html"
    hide_ordering_field = True
    fields = ("preview", "image", "sort")
    readonly_fields = ("preview",)

    @admin.display(description="фото")
    def preview(self, obj):
        return photo_preview(obj.image)


class GoodsSpecInline(TabularInline):
    model = GoodsSpec
    extra = 1
    tab = True
    ordering_field = "sort"
    template_before = "admin/catalog/ordering_hint.html"
    hide_ordering_field = True
    fields = ("name", "value", "sort")


@admin.register(GoodsCategory)
class GoodsCategoryAdmin(ModelAdmin):
    list_display = ("name", "sort")
    list_editable = ("sort",)
    search_fields = ("name",)


@admin.register(Goods)
class GoodsAdmin(PhotoPreviewMixin, ModelAdmin):
    list_filter_submit = True
    list_fullwidth = True
    compressed_fields = True
    list_display = ("thumbnail", "title", "category", "price_rub", "availability", "is_published", "sort")
    list_display_links = ("thumbnail", "title")
    list_editable = ("price_rub", "availability", "is_published", "sort")
    list_filter = ("category", "availability", "is_published")
    search_fields = ("title", "description")
    autocomplete_fields = ("category",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [GoodsPhotoInline, GoodsSpecInline]
    fieldsets = (
        ("Основное", {"classes": ("tab",), "fields": ("title", "category", "tagline", "description")}),
        ("Цена и наличие", {"classes": ("tab",), "fields": ("price_rub", "availability", "lead_time")}),
        ("Публикация", {"classes": ("tab",), "fields": ("is_published", "sort", "slug", "created_at", "updated_at")}),
    )

    def view_on_site(self, obj):
        return f"/goods/{obj.slug}"
