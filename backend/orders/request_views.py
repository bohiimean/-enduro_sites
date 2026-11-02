from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .models import PurchaseRequest
from .request_serializers import PurchaseRequestInputSerializer, PurchaseRequestSerializer
from .request_services import submit_request


class RequestCreateThrottle(UserRateThrottle):
    scope = "purchase_request"


class PurchaseRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = PurchaseRequestSerializer

    def get_queryset(self):
        return PurchaseRequest.objects.filter(user=self.request.user).prefetch_related("items")

    def get_throttles(self):
        return [RequestCreateThrottle()] if self.request.method == "POST" else []

    def create(self, request, *args, **kwargs):
        serializer = PurchaseRequestInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj, created = submit_request(request.user, serializer.validated_data)
        return Response(PurchaseRequestSerializer(obj).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class PurchaseRequestDetailView(generics.RetrieveAPIView):
    serializer_class = PurchaseRequestSerializer

    def get_queryset(self):
        return PurchaseRequest.objects.filter(user=self.request.user).prefetch_related("items")


class RequestContactView(APIView):
    def get(self, request):
        previous = PurchaseRequest.objects.filter(user=request.user).first()
        if previous:
            return Response({"name": previous.name, "phone": previous.phone})
        phone = request.user.phones.filter(verified_at__isnull=False).first() or request.user.phones.first()
        return Response({"name": request.user.full_name, "phone": phone.phone if phone else ""})
