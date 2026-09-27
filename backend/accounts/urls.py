from django.urls import path

from .views import PhoneDestroyView, PhoneListCreateView, ProfileView

urlpatterns = [
    path("me/", ProfileView.as_view(), name="account-me"),
    path("phones/", PhoneListCreateView.as_view(), name="account-phones"),
    path("phones/<int:pk>/", PhoneDestroyView.as_view(), name="account-phone-detail"),
]
