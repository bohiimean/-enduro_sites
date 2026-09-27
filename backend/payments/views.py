"""API оплаты: статус KYC, загрузка документов, платёж и его статус.

Порядок шагов — как у бота и сознательно не как в доках alfabit: телефон →
KYC → сумма → создание платежа → QR. В доках платёж создаётся первым и
возвращает `kyc_required`, но тогда зафиксированный курс жил бы весь KYC, а
верификация может уйти на ручную сверку. Окно фиксации курса — от QR до оплаты.

Доступ: всё закрыто по умолчанию (`IsAuthenticated` в настройках DRF), выборки
только от `request.user`. Телефон берётся из номеров, привязанных к аккаунту,
по id — номер из тела запроса ничего не открывает.

`Payment.user` при этом nullable: если понадобится гостевой сценарий, это
будет снятие проверки доступа, а не вторая реализация флоу (CLAUDE.md).
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from accounts.models import PhoneNumber

from .alfabit import TRANSPORT_ERROR_CODES, AlfabitError, get_client, is_access_error
from .kyc_trace import log_upload, mask_phone
from .models import KycDocument, Payer, Payment
from .pricing import PriceUnavailable, payment_price
from .serializers import (
    MAX_RUB_PER_DAY,
    MAX_RUB_PER_OPERATION,
    DocumentsUploadSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
    kyc_state,
)
from .services import apply_payer_state, refresh_payer, refresh_payment
from .uploads import MAX_REQUEST_BYTES, memory_only

logger = logging.getLogger(__name__)

# Статус у alfabit не спрашиваем чаще, чем раз в столько секунд на запись:
# фронт опрашивает нас каждые несколько секунд, alfabit дёргать так часто незачем.
_REFRESH_EVERY = timedelta(seconds=3)
# Неоплаченный платёж ещё держит дневной лимит — пока жив его QR.
_UNPAID_HOLDS_LIMIT = timedelta(minutes=30)


def client_ip(request) -> str:
    """Настоящий IP плательщика — то, чего у бота не было. Мы за nginx, он
    кладёт адрес клиента в X-Real-IP; сам backend наружу не опубликован."""
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")


class Unavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Оплата сейчас недоступна. Напишите менеджеру — оформим вручную."
    default_code = "payments_unavailable"


class ProviderError(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = "provider_error"


def _provider_error(exc: AlfabitError) -> APIException:
    """Текст ошибки для человека. Транспортные коды прячем: «NETWORK:
    ConnectionError» ничего не объясняет, ошибки доступа — тем более."""
    if is_access_error(exc):
        logger.error("alfabit: доступ запрещён (%s)", exc)
        return Unavailable()
    if exc.code in TRANSPORT_ERROR_CODES:
        return ProviderError("Платёжный сервис не отвечает, попробуйте через пару минут.")
    return ProviderError(exc.message or exc.code)


def _client():
    client = get_client()
    if client is None:
        raise Unavailable()
    return client


def _own_phone(request, phone_id) -> PhoneNumber:
    return get_object_or_404(PhoneNumber, pk=phone_id, user=request.user)


# --- Лимиты частоты -----------------------------------------------------------
# Статус KYC по номеру — чувствительный запрос: пусть и только по своим
# номерам, но номер можно привязать, посмотреть и отвязать. Поэтому лимит и
# на аккаунт, и на IP (CLAUDE.md, этап 5).


class _UserThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class _IpThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class KycUserThrottle(_UserThrottle):
    scope = "kyc_user"


class KycIpThrottle(_IpThrottle):
    scope = "kyc_ip"


class UploadThrottle(_UserThrottle):
    scope = "kyc_upload"


class PaymentCreateThrottle(_UserThrottle):
    scope = "payment_create"


# --- KYC ----------------------------------------------------------------------


class KycStatusView(APIView):
    """Статус верификации по своему номеру. Спрашивает alfabit, если запись
    не обновлялась последние секунды."""

    throttle_classes = [KycUserThrottle, KycIpThrottle]

    def get(self, request, phone_id: int):
        phone = _own_phone(request, phone_id)
        payer = Payer.objects.filter(phone=phone.phone).first()
        fresh_enough = (
            payer is not None
            and payer.last_checked_at is not None
            and timezone.now() - payer.last_checked_at < _REFRESH_EVERY
        )
        if not fresh_enough:
            try:
                payer = refresh_payer(
                    _client(), phone.phone, user_id=request.user.pk, event="status"
                )
            except AlfabitError as exc:
                if payer is None:
                    raise _provider_error(exc) from exc
                # Есть прошлое состояние — отдаём его, а не ошибку.
                logger.warning("kyc status: phone=%s: %s", mask_phone(phone.phone), exc)
        return Response(kyc_state(payer, request.user))


class DocumentsUploadView(APIView):
    """Фото паспорта: обе страницы одним запросом, потоком в alfabit.

    Комплектом, как у бота: половина комплекта в alfabit — заявка в вечном
    pending, из которой обычный сценарий не выпускает. Байты не ложатся ни в
    MEDIA, ни во временные файлы (см. uploads.py и nginx).
    """

    throttle_classes = [UploadThrottle]

    def initialize_request(self, request, *args, **kwargs):
        # До разбора тела — дальше Django уже выбрал бы обработчики сам.
        memory_only(request)
        return super().initialize_request(request, *args, **kwargs)

    def post(self, request):
        if int(request.META.get("CONTENT_LENGTH") or 0) > MAX_REQUEST_BYTES:
            return Response(
                {"detail": "Файлы слишком большие: не больше 20 МБ каждый."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        serializer = DocumentsUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        phone = _own_phone(request, data["phone_id"])
        client = _client()

        payer, _ = Payer.objects.get_or_create(phone=phone.phone)
        if payer.manual_review:
            # Дока прямо запрещает переотправку тех же файлов, пока заявку
            # смотрит оператор.
            return Response(
                {"detail": "Документы проверяет сотрудник. Присылать их заново не нужно."},
                status=status.HTTP_409_CONFLICT,
            )
        if payer.is_approved:
            return Response(kyc_state(payer, request.user))

        consent_at = timezone.now()
        ip = client_ip(request)
        for doc_type in (KycDocument.TYPE_MAIN, KycDocument.TYPE_REGISTRATION):
            file = data[doc_type]
            try:
                result = client.upload_payer_document(
                    phone.phone, doc_type, file, file.name or f"{doc_type}.jpg",
                    payer_ip=ip, content_type=file.content_type or "image/jpeg",
                )
            except AlfabitError as exc:
                logger.warning("kyc upload: phone=%s doc=%s: %s", mask_phone(phone.phone), doc_type, exc)
                raise _provider_error(exc) from exc
            finally:
                file.close()
            log_upload("upload", user_id=request.user.pk, phone=phone.phone, doc_type=doc_type, result=result)
            # low_confidence приходит только здесь — второго шанса не будет.
            KycDocument.objects.create(
                payer=payer,
                doc_type=doc_type,
                uploaded_by=request.user,
                consent_at=consent_at,
                low_confidence=result.get("low_confidence"),
                response={k: v for k, v in result.items() if k != "expected_payer_name"},
            )
            apply_payer_state(payer, result)

        # Результат досмотрит worker — даже если человек закроет вкладку.
        if not payer.is_final:
            payer.watch_since = timezone.now()
            payer.save(update_fields=["watch_since", "updated_at"])
        return Response(kyc_state(payer, request.user), status=status.HTTP_201_CREATED)


# --- Платёж -------------------------------------------------------------------


class PaymentListCreateView(generics.ListAPIView):
    serializer_class = PaymentSerializer

    def get_throttles(self):
        if self.request.method == "POST":
            return [PaymentCreateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user).select_related("payer")

    def post(self, request):
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = _own_phone(request, serializer.validated_data["phone_id"])
        amount_cny: Decimal = serializer.validated_data["amount_cny"]
        client = _client()

        # KYC спрашиваем заново: между «одобрено» на экране и нажатием кнопки
        # статус мог измениться, а создавать платёж по старому статусу незачем.
        try:
            payer = refresh_payer(client, phone.phone, user_id=request.user.pk, event="before payment")
        except AlfabitError as exc:
            raise _provider_error(exc) from exc
        if not payer.is_approved:
            return Response(
                {"detail": "Сначала нужно пройти верификацию.", "kyc": kyc_state(payer, request.user)},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            price = payment_price(amount_cny)
        except PriceUnavailable as exc:
            logger.warning("payment: курс недоступен: %s", exc)
            return Response(
                {"detail": "Курс сейчас недоступен. Попробуйте через несколько минут."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        amount_rub = price.rub_for(amount_cny)

        if amount_rub > MAX_RUB_PER_OPERATION:
            return Response(
                {"detail": f"Не больше {MAX_RUB_PER_OPERATION:,.0f} ₽ за операцию — "
                           f"по текущему курсу это {amount_rub:,.2f} ₽.".replace(",", " ")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        now = timezone.now()
        used = (
            Payment.objects.filter(phone=phone.phone, created_at__gte=now - timedelta(hours=24))
            .filter(
                Q(status=Payment.STATUS_PAID)
                | Q(status=Payment.STATUS_CREATED, created_at__gte=now - _UNPAID_HOLDS_LIMIT)
            )
            .aggregate(total=Sum("amount_rub"))["total"]
        ) or Decimal(0)
        if used + amount_rub > MAX_RUB_PER_DAY:
            left = max(MAX_RUB_PER_DAY - used, Decimal(0))
            return Response(
                {"detail": f"Суточный лимит {MAX_RUB_PER_DAY:,.0f} ₽ по этому номеру: "
                           f"осталось {left:,.2f} ₽.".replace(",", " ")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Запись появляется до обращения к alfabit: если ответ потеряется,
        # след платежа у нас всё равно останется.
        payment = Payment.objects.create(
            external_payment_id=f"W{request.user.pk}-{uuid.uuid4().hex[:12]}",
            user=request.user,
            payer=payer,
            phone=phone.phone,
            amount_cny=amount_cny,
            amount_rub=amount_rub,
            rate_used=price.rate.quantize(Decimal("0.000001")),
            price_per_cny=price.price_per_cny,
            payer_ip=client_ip(request) or None,
            payer_user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        )
        try:
            result = client.create_checkout_payment(
                amount=f"{amount_rub:.2f}",
                payer_phone=phone.phone,
                payer_ip=payment.payer_ip or "",
                external_payment_id=payment.external_payment_id,
                description=f"Покупка {amount_cny} CNY",
                payer_user_agent=payment.payer_user_agent or None,
            )
        except AlfabitError as exc:
            payment.status = Payment.STATUS_FAILED
            payment.provider_status = exc.code[:32]
            payment.save(update_fields=["status", "provider_status"])
            logger.warning("payment create: ext=%s: %s", payment.external_payment_id, exc)
            raise _provider_error(exc) from exc

        if result.get("status") == "kyc_required":
            # Статус успел смениться между approved и созданием платежа — редко,
            # но тогда человеку обратно в шаг верификации.
            payment.status = Payment.STATUS_FAILED
            payment.provider_status = "kyc_required"
            payment.raw_response = result
            payment.save(update_fields=["status", "provider_status", "raw_response"])
            apply_payer_state(payer, result)
            return Response(
                {"detail": "Нужно пройти верификацию заново.", "kyc": kyc_state(payer, request.user)},
                status=status.HTTP_409_CONFLICT,
            )

        payment.payment_uid = str(result.get("payment_uid") or "")[:64]
        if not payment.payment_uid:
            logger.error("payment create: нет payment_uid ext=%s ответ=%s", payment.external_payment_id, result)
            payment.status = Payment.STATUS_FAILED
            payment.raw_response = result
            payment.save(update_fields=["status", "raw_response"])
            raise ProviderError("Сервис оплаты вернул неожиданный ответ. Напишите менеджеру.")
        payment.save(update_fields=["payment_uid"])
        logger.info(
            "payment created: user=%s ext=%s uid=%s %s ₽ (%s CNY) rate=%s fresh=%s",
            request.user.pk, payment.external_payment_id, payment.payment_uid,
            amount_rub, amount_cny, price.rate, price.fresh,
        )
        # QR появляется у alfabit за секунды — фронт заберёт его опросом.
        return Response(
            PaymentSerializer(payment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class PaymentDetailView(generics.RetrieveAPIView):
    """Статус платежа. Пока он не закрыт, заодно спрашиваем alfabit — кнопки
    «Я оплатил» на сайте нет, фронт просто опрашивает этот адрес."""

    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user).select_related("payer")

    def get_object(self):
        payment = super().get_object()
        stale = payment.last_checked_at is None or (
            timezone.now() - payment.last_checked_at >= _REFRESH_EVERY
        )
        if not payment.is_final and payment.payment_uid and stale:
            client = get_client()
            if client is not None:
                try:
                    refresh_payment(client, payment)
                except AlfabitError as exc:
                    # Отдаём то, что знаем; worker досмотрит.
                    logger.warning("payment detail: ext=%s: %s", payment.external_payment_id, exc)
        return payment
