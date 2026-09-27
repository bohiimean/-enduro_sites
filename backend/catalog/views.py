from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Product
from .serializers import ProductSerializer


class ProductListView(generics.ListAPIView):
    # По умолчанию в проекте API закрыто (IsAuthenticated). Каталог —
    # публичная витрина, открываем явно.
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    queryset = (
        Product.objects.filter(is_published=True)
        .select_related("brand")
        .prefetch_related("photos")
    )


class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    lookup_field = "slug"
    queryset = (
        Product.objects.filter(is_published=True)
        .select_related("brand")
        .prefetch_related("photos")
    )
