from rest_framework import serializers

from core.phone import to_e164
from .models import PurchaseRequest, PurchaseRequestItem


class RequestItemInputSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["bike", "goods"])
    product_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    offer = serializers.ChoiceField(choices=["stock", "order"])
    quantity = serializers.IntegerField(min_value=1, max_value=99)


class PurchaseRequestInputSerializer(serializers.Serializer):
    submission_key = serializers.UUIDField()
    name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=32)
    city = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    payment_method = serializers.ChoiceField(choices=PurchaseRequest.PAYMENT_METHODS, required=False, allow_blank=True, default="")
    items = RequestItemInputSerializer(many=True, allow_empty=False, max_length=50)

    def validate_phone(self, value):
        phone = to_e164(value)
        if not phone:
            raise serializers.ValidationError("Нужен российский номер, например +7 912 345-67-89.")
        return phone

    def validate_items(self, items):
        keys = [(item["kind"], item["product_id"], item["offer"]) for item in items]
        if len(keys) != len(set(keys)):
            raise serializers.ValidationError("Объедините одинаковые позиции в одну строку.")
        return items


class PurchaseRequestItemSerializer(serializers.ModelSerializer):
    offer_label = serializers.CharField(source="get_offer_display", read_only=True)

    class Meta:
        model = PurchaseRequestItem
        fields = ["id", "kind", "title", "offer", "offer_label", "quantity", "unit_price_rub"]


class PurchaseRequestSerializer(serializers.ModelSerializer):
    payment_method_label = serializers.CharField(source="get_payment_method_display", read_only=True)
    status_label = serializers.CharField(source="client_status", read_only=True)
    items = PurchaseRequestItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseRequest
        fields = ["id", "name", "phone", "status", "status_label", "created_at", "items", "city", "payment_method", "payment_method_label"]
