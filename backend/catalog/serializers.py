from rest_framework import serializers

from .models import Brand, Product, ProductPhoto


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "slug"]


class ProductPhotoSerializer(serializers.ModelSerializer):
    url = serializers.ImageField(source="image", read_only=True)

    class Meta:
        model = ProductPhoto
        fields = ["id", "url", "sort"]


class ProductSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    photos = ProductPhotoSerializer(many=True, read_only=True)
    title = serializers.CharField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "slug", "title", "brand", "model", "color",
            "price", "description", "in_stock", "photos",
        ]
