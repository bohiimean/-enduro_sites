from django.db.models import Q
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CatalogSettings, Goods, GoodsCategory, Product
from .pricing import current_rate
from .serializers import CatalogTermsSerializer, GoodsCategorySerializer, GoodsSerializer, ProductSerializer

# Незнакомое значение фильтра не ошибка, а просто весь каталог: адрес
# могли набрать руками или сохранить в закладках со старым параметром.
AVAILABILITY = {
    "stock": Q(stock_qty__gt=0),
    "order": Q(is_orderable=True),
}
POWERTRAIN = {
    "ice": Q(powertrain__in=[Product.ICE_2T, Product.ICE_4T]),
    "electric": Q(powertrain=Product.ELECTRIC),
}


class CatalogViewMixin:
    # По умолчанию в проекте API закрыто (IsAuthenticated). Каталог —
    # публичная витрина, открываем явно.
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    queryset = (
        Product.objects.filter(is_published=True)
        .select_related("brand")
        .prefetch_related("photos", "extra_specs")
    )

    def get_serializer_context(self):
        # Курс один на весь ответ: считаем его здесь, а не в каждой карточке.
        context = super().get_serializer_context()
        config = CatalogSettings.load()
        context["catalog_config"] = config
        context["catalog_rate"] = current_rate(config)
        return context


class ProductListView(CatalogViewMixin, generics.ListAPIView):
    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        for options, key in ((AVAILABILITY, "availability"), (POWERTRAIN, "powertrain")):
            condition = options.get(params.get(key, ""))
            if condition is not None:
                queryset = queryset.filter(condition)
        return queryset


class ProductDetailView(CatalogViewMixin, generics.RetrieveAPIView):
    lookup_field = "slug"


class CatalogTermsView(APIView):
    """Курс юаня каталога и наценка под заказ — для шапки сайта.

    Главная обещает «предзаказ с фиксированной наценкой 5%». Цифра берётся
    отсюда, а не пишется во фронтенде: иначе правка наценки в админке оставила
    бы на сайте старое обещание.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        config = CatalogSettings.load()
        terms = {"order_markup_percent": config.order_markup_percent, "rate": current_rate(config)}
        return Response(CatalogTermsSerializer(terms).data)


class GoodsViewMixin:
    permission_classes = [AllowAny]
    serializer_class = GoodsSerializer
    queryset = (
        Goods.objects.filter(is_published=True)
        .select_related("category").prefetch_related("photos", "specs")
    )


class GoodsListView(GoodsViewMixin, generics.ListAPIView):
    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("availability") in ("stock", "order"):
            queryset = queryset.filter(availability=params["availability"])
        category = params.get("category", "")
        if category.isascii() and category.isdecimal() and len(category) <= 18:
            queryset = queryset.filter(category_id=category)
        return queryset


class GoodsDetailView(GoodsViewMixin, generics.RetrieveAPIView):
    lookup_field = "slug"


class GoodsCategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = GoodsCategorySerializer
    pagination_class = None
    queryset = GoodsCategory.objects.filter(goods__is_published=True).distinct()


class ProductByIdView(CatalogViewMixin, generics.RetrieveAPIView):
    pass


class GoodsByIdView(GoodsViewMixin, generics.RetrieveAPIView):
    pass
