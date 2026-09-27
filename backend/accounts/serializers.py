"""Сериализаторы кабинета.

Всё здесь читается и пишется только для `request.user`. Телефон из запроса —
это ввод пользователя, а не удостоверение: по нему ничего не ищется и ничего не
открывается (CLAUDE.md, «Как реализуется аутентификация»).
"""
from allauth.account.utils import has_verified_email
from rest_framework import serializers

from core.phone import to_e164

from .models import PhoneNumber, User


class PhoneNumberSerializer(serializers.ModelSerializer):
    verified = serializers.BooleanField(source="is_verified", read_only=True)
    # Поле объявлено руками по двум причинам.
    # Первая: у модели `phone` уникальный, и DRF добавил бы к нему свою проверку
    # уникальности с ответом 400 «уже существует». Занятый номер — это не ошибка
    # формата, а конфликт, и отвечать на него должно 409 с понятным текстом
    # (см. views.PhoneTaken).
    # Вторая: длину нельзя брать с модели. В базе лежит нормализованный
    # +7XXXXXXXXXX (12 символов), а человек вводит «+7 (912) 345-67-89» — это 18,
    # и проверка длины отбила бы номер раньше, чем его нормализует validate_phone.
    phone = serializers.CharField(max_length=32)

    class Meta:
        model = PhoneNumber
        fields = ["id", "phone", "verified", "verification_method", "created_at"]
        # Подтверждение ставит канал (этап 6), а не пользователь.
        read_only_fields = ["verification_method", "created_at"]

    def validate_phone(self, value: str) -> str:
        normalized = to_e164(value)
        if not normalized:
            raise serializers.ValidationError(
                "Нужен российский номер, например +7 912 345-67-89."
            )
        return normalized


class ProfileSerializer(serializers.ModelSerializer):
    # Подтверждение адреса живёт в модели allauth (`EmailAddress.verified`).
    # Своего флага на User нет и быть не должно — иначе два источника истины.
    email_verified = serializers.SerializerMethodField()
    phones = PhoneNumberSerializer(many=True, read_only=True)
    has_verified_phone = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ["email", "email_verified", "full_name", "phones", "has_verified_phone"]
        # Смена адреса — это отдельный сценарий allauth с подтверждением нового
        # адреса, а не правка поля профиля.
        read_only_fields = ["email"]

    def get_email_verified(self, obj: User) -> bool:
        return has_verified_email(obj, obj.email)
