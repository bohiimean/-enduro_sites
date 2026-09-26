from django.urls import path

from .views import PricingView

urlpatterns = [path("", PricingView.as_view(), name="pricing")]
