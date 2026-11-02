from django.urls import path

from .views import (
    CatalogTermsView, GoodsCategoryListView, GoodsDetailView, GoodsListView,
    ProductDetailView, ProductListView, ProductByIdView, GoodsByIdView,
)

urlpatterns = [
    path("products/by-id/<int:pk>/", ProductByIdView.as_view(), name="product-by-id"),
    path("goods/by-id/<int:pk>/", GoodsByIdView.as_view(), name="goods-by-id"),
    path("goods/", GoodsListView.as_view(), name="goods-list"),
    path("goods/<slug:slug>/", GoodsDetailView.as_view(), name="goods-detail"),
    path("goods-categories/", GoodsCategoryListView.as_view(), name="goods-category-list"),
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/<slug:slug>/", ProductDetailView.as_view(), name="product-detail"),
    path("terms/", CatalogTermsView.as_view(), name="catalog-terms"),
]
