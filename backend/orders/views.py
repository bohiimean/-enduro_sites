"""Заказы в кабинете: номер для заказов и список заказов по нему.

Доступ закрыт по умолчанию (`IsAuthenticated` в настройках DRF). Номер из
запроса открывает заказы только один раз — когда аккаунт указывает его
впервые. Дальше он зафиксирован, и запрос с другим номером становится заявкой
менеджеру, а не поиском (см. `OrderPhone`).
"""
from django.db import IntegrityError
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import OrderPhone, orders_for
from .serializers import OrderPhoneInputSerializer, OrderPhoneSerializer, OrderSerializer


class OrderPhoneTaken(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = (
        "Этот номер уже указан в другом аккаунте. Если номер ваш — напишите менеджеру."
    )
    default_code = "order_phone_taken"


class OrderPhoneView(APIView):
    """GET — текущий номер и заявка на смену; POST — указать номер или, если
    он уже указан, попросить сменить."""

    def get(self, request):
        current = OrderPhone.objects.filter(user=request.user).first()
        if current is None:
            return Response({"phone": None, "requested_phone": "", "requested_at": None})
        return Response(OrderPhoneSerializer(current).data)

    def post(self, request):
        serializer = OrderPhoneInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        if OrderPhone.objects.filter(phone=phone).exclude(user=request.user).exists():
            raise OrderPhoneTaken()

        current = OrderPhone.objects.filter(user=request.user).first()
        if current is not None:
            current.request_change(phone)
            return Response(OrderPhoneSerializer(current).data)

        try:
            # get_or_create, а не create: двойной клик того же аккаунта
            # получает уже записанный номер, а не ошибку.
            current, created = OrderPhone.objects.get_or_create(
                user=request.user, defaults={"phone": phone}
            )
        except IntegrityError:
            # Номер заняли между проверкой выше и записью.
            raise OrderPhoneTaken()
        return Response(
            OrderPhoneSerializer(current).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    # Заказов у человека единицы — постраничность фронту только мешает.
    pagination_class = None

    def get_queryset(self):
        return orders_for(self.request.user)
