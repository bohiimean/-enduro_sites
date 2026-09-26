from rest_framework import generics

from .models import Product
from .serializers import ProductSerializer


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    queryset = (
        Product.objects.filter(is_published=True)
        .select_related("brand")
        .prefetch_related("photos")
    )


class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductSerializer
    lookup_field = "slug"
    queryset = (
        Product.objects.filter(is_published=True)
        .select_related("brand")
        .prefetch_related("photos")
    )
