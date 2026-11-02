from django.urls import path
from .request_views import PurchaseRequestDetailView, PurchaseRequestListCreateView, RequestContactView

urlpatterns = [
    path("", PurchaseRequestListCreateView.as_view(), name="purchase-request-list"),
    path("contact/", RequestContactView.as_view(), name="purchase-request-contact"),
    path("<int:pk>/", PurchaseRequestDetailView.as_view(), name="purchase-request-detail"),
]
