from django.urls import path

from .views import CatalogTermsView, ProductDetailView, ProductListView

urlpatterns = [
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/<slug:slug>/", ProductDetailView.as_view(), name="product-detail"),
    path("terms/", CatalogTermsView.as_view(), name="catalog-terms"),
]
