from django.contrib import admin

from .models import Brand, Product, ProductPhoto


class ProductPhotoInline(admin.TabularInline):
    model = ProductPhoto
    extra = 1
    fields = ("image", "source_url", "sort")


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
    list_display = ("title", "color", "price", "in_stock", "is_published", "sort", "updated_at")
    list_filter = ("brand", "in_stock", "is_published")
    list_editable = ("in_stock", "is_published", "sort")
    search_fields = ("model", "color", "brand__name", "external_key")
    autocomplete_fields = ("brand",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [ProductPhotoInline]
