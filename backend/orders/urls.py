from django.urls import path

from .views import OrderListView, OrderPhoneView

urlpatterns = [
    path("", OrderListView.as_view(), name="order-list"),
    path("phone/", OrderPhoneView.as_view(), name="order-phone"),
]
