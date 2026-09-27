from django.urls import path

from .views import DocumentsUploadView, KycStatusView, PaymentDetailView, PaymentListCreateView

urlpatterns = [
    path("", PaymentListCreateView.as_view(), name="payment-list"),
    path("<int:pk>/", PaymentDetailView.as_view(), name="payment-detail"),
    path("kyc/<int:phone_id>/", KycStatusView.as_view(), name="payment-kyc"),
    # Путь совпадает с отдельной location в nginx: там выключена буферизация
    # тела запроса на диск (CLAUDE.md, раздел 152-ФЗ).
    path("documents/", DocumentsUploadView.as_view(), name="payment-documents"),
]
