"""Заказы в кабинете — те же поля, что бот показывает по «📦 Статус заказа»,
плюс цена и оплачено: остаток без них непонятно, откуда взялся.

Комментарий менеджера и ключ импорта наружу не отдаются — это служебное.
"""
from rest_framework import serializers

from core.phone import to_e164

from .models import Order, OrderPhone


class OrderSerializer(serializers.ModelSerializer):
    remainder = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    status = serializers.CharField(source="supply_status.name", default="", read_only=True)
    status_final = serializers.BooleanField(
        source="supply_status.is_final", default=False, read_only=True
    )

    class Meta:
        model = Order
        fields = [
            "id", "title", "color", "quantity",
            "full_name", "phone", "city", "delivery_company",
            "price", "paid", "remainder",
            "status", "status_final", "ordered_at",
        ]


class OrderPhoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderPhone
        fields = ["phone", "requested_phone", "requested_at"]


class OrderPhoneInputSerializer(serializers.Serializer):
    # Длина не с модели: человек вводит «+7 (912) 345-67-89», а в базе
    # нормализованный +7XXXXXXXXXX (см. accounts.PhoneNumberSerializer).
    phone = serializers.CharField(max_length=32)

    def validate_phone(self, value: str) -> str:
        normalized = to_e164(value)
        if not normalized:
            raise serializers.ValidationError(
                "Нужен российский номер, например +7 912 345-67-89."
            )
        return normalized
