from decimal import Decimal

from rest_framework import serializers

from .models import KycDocument, Payer, Payment

# Лимиты alfabit. Показываются человеку до ввода суммы (CLAUDE.md, «Оплата»).
MAX_RUB_PER_OPERATION = Decimal("100000")
MAX_RUB_PER_DAY = Decimal("100000")


def kyc_state(payer: Payer, user) -> dict:
    """Состояние верификации для экрана оплаты.

    ФИО по паспорту здесь нет сознательно: его видно только на шаге QR и
    только тому, кто сам загружал документы (см. PaymentSerializer).
    """
    docs = payer.documents.filter(uploaded_by=user).order_by("-uploaded_at")
    latest: dict[str, KycDocument] = {}
    for doc in docs:
        latest.setdefault(doc.doc_type, doc)
    status = payer.kyc_status
    # Три разных «pending»: идёт распознавание; заявку забрал оператор
    # (переотправка тех же файлов запрещена докой); ждём недостающий документ.
    can_upload = status == Payer.STATUS_NOT_STARTED or (
        status == Payer.STATUS_PENDING and not payer.processing and not payer.manual_review
    )
    return {
        "phone": payer.phone,
        "kyc_status": status,
        "processing": payer.processing,
        "manual_review": payer.manual_review,
        "can_upload": can_upload,
        "documents": [
            {
                "doc_type": d.doc_type,
                "uploaded_at": d.uploaded_at,
                "low_confidence": d.low_confidence,
            }
            for d in latest.values()
        ],
        "limits": {
            "per_operation_rub": MAX_RUB_PER_OPERATION,
            "per_day_rub": MAX_RUB_PER_DAY,
        },
    }


class DocumentsUploadSerializer(serializers.Serializer):
    phone_id = serializers.IntegerField()
    passport_main = serializers.FileField()
    passport_registration = serializers.FileField()
    # Явное согласие на обработку персданных (152-ФЗ). Без галочки не шлём.
    consent = serializers.BooleanField()

    def validate_consent(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("Нужно согласие на обработку персональных данных.")
        return value

    def _validate_image(self, file):
        content_type = (file.content_type or "").lower()
        if not (content_type.startswith("image/") or content_type == "application/pdf"):
            raise serializers.ValidationError("Нужна фотография или PDF.")
        return file

    validate_passport_main = _validate_image
    validate_passport_registration = _validate_image


class PaymentCreateSerializer(serializers.Serializer):
    phone_id = serializers.IntegerField()
    amount_cny = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("1")
    )


class PaymentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payer_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "external_payment_id", "phone", "amount_cny", "amount_rub",
            "price_per_cny", "status", "status_display", "qr_url", "qr_payload",
            "payer_name", "created_at", "paid_at",
        ]
        read_only_fields = fields

    def get_payer_name(self, obj: Payment) -> str | None:
        """ФИО плательщика — на шаге QR, чтобы человек платил с карты на своё
        имя. Только аккаунту, который сам загружал документы."""
        if obj.status != Payment.STATUS_CREATED or obj.payer is None:
            return None
        user = self.context["request"].user
        if not obj.payer.name_visible_to(user):
            return None
        return obj.payer.expected_payer_name or None
