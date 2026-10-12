from rest_framework import serializers

from .models import Brand, Product, ProductPhoto
from .pricing import offers
from .specs import highlights, spec_groups


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "slug"]


class ProductPhotoSerializer(serializers.ModelSerializer):
    # Адрес относительный, а не собранный по хосту запроса: страницу каталога
    # рендерит Nuxt на сервере, его запрос приходит на `backend:8000`, и в HTML
    # уехал бы адрес, недоступный браузеру. Относительный путь браузер берёт
    # через nginx.
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProductPhoto
        fields = ["id", "url", "sort"]

    def get_url(self, photo: ProductPhoto) -> str:
        return photo.image.url


class SpecItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    value = serializers.CharField()


class SpecGroupSerializer(serializers.Serializer):
    title = serializers.CharField()
    items = SpecItemSerializer(many=True)


class StockOfferSerializer(serializers.Serializer):
    qty = serializers.IntegerField()
    price_rub = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)


class OrderOfferSerializer(serializers.Serializer):
    price_rub = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    lead_time = serializers.CharField()


class RateSerializer(serializers.Serializer):
    price_per_cny = serializers.DecimalField(max_digits=12, decimal_places=2)
    fetched_at = serializers.DateTimeField()


class ProductSerializer(serializers.ModelSerializer):
    """Карточка байка. Цены считаются по курсу, который view берёт один раз
    на запрос и кладёт в контекст: `catalog_config` и `catalog_rate`."""

    brand = BrandSerializer(read_only=True)
    photos = ProductPhotoSerializer(many=True, read_only=True)
    title = serializers.CharField(read_only=True)
    powertrain_label = serializers.CharField(source="get_powertrain_display", read_only=True)
    documents_label = serializers.CharField(source="get_documents_display", read_only=True)
    highlights = serializers.SerializerMethodField()
    specs = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "slug", "title", "brand", "model", "model_year",
            "powertrain", "powertrain_label", "tagline", "description", "colors",
            "documents", "documents_label", "highlights", "specs", "photos",
        ]

    def get_highlights(self, product: Product) -> list[str]:
        return highlights(product)

    def get_specs(self, product: Product) -> list[dict]:
        return SpecGroupSerializer(spec_groups(product), many=True).data

    def to_representation(self, product: Product) -> dict:
        data = super().to_representation(product)
        found = offers(product, self.context["catalog_config"], self.context["catalog_rate"])
        data["stock"] = StockOfferSerializer(found.stock).data if found.stock else None
        data["order"] = OrderOfferSerializer(found.order).data if found.order else None
        data["rate"] = RateSerializer(found.rate).data if found.rate else None
        return data
