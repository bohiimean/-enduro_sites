"""Синхронизация с alfabit: статус плательщика (KYC) и статус платежа.

Одни и те же функции зовут и API (человек смотрит на экран оплаты), и `worker`
(человек закрыл вкладку). Состояние всегда пишется в БД — у бота оно жило в
памяти и терялось при рестарте.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from .alfabit import AlfabitClient, AlfabitError
from .kyc_trace import log_payer, mask_phone
from .models import Payer, Payment

logger = logging.getLogger(__name__)

# Статусы платежа у alfabit. Написание у них плавает, поэтому множества, а не
# одно значение (перенесено из бота, `handlers/payment.py`).
PAID_STATUSES = frozenset({"paid", "succeeded", "success", "completed"})
FAILED_STATUSES = frozenset({"expired", "failed", "canceled", "cancelled", "rejected"})

# Дольше этого заявку KYC не досматриваем: ручная сверка занимает часы, а не
# дни, и бесконечно дёргать API по забытому номеру незачем. Снятие с
# наблюдения пишется в лог — это тот случай, который стоит разобрать руками.
KYC_WATCH_MAX_AGE = timedelta(hours=72)
# Неоплаченный платёж опрашиваем сутки. Реквизиты СБП живут меньше, так что
# дальше — это уже разбор менеджером, а не ожидание.
PAYMENT_WATCH_MAX_AGE = timedelta(hours=24)


def apply_payer_state(payer: Payer, data: dict) -> Payer:
    """Записать ответ alfabit по плательщику. Поля, которых в ответе нет, не
    трогаем: ответ на загрузку документа, например, приходит без ФИО."""
    status = data.get("kyc_status") or data.get("payer_status")
    if status in dict(Payer.STATUS_CHOICES):
        payer.kyc_status = status
    if "processing" in data:
        payer.processing = bool(data["processing"])
    if "manual_review" in data:
        payer.manual_review = bool(data["manual_review"])
    if data.get("expected_payer_name"):
        payer.expected_payer_name = data["expected_payer_name"]
    payer.last_checked_at = timezone.now()
    if payer.is_final:
        payer.watch_since = None
    payer.save()
    return payer


def refresh_payer(client: AlfabitClient, phone: str, *, user_id: int | None, event: str) -> Payer:
    """Спросить alfabit о плательщике и записать ответ. Бросает AlfabitError."""
    data = client.get_payer(phone)
    log_payer(event, user_id=user_id, phone=phone, payer=data)
    payer, _ = Payer.objects.get_or_create(phone=phone)
    return apply_payer_state(payer, data)


def apply_payment_state(payment: Payment, data: dict) -> Payment:
    raw = str(data.get("status") or "").lower()
    payment.provider_status = raw[:32]
    payment.raw_response = data
    payment.last_checked_at = timezone.now()
    if data.get("qr_url"):
        payment.qr_url = data["qr_url"]
    if data.get("qr_payload"):
        payment.qr_payload = data["qr_payload"]

    # Из «оплачен» назад не откатываемся ни при каком ответе: деньги уже у
    # alfabit, и менеджер мог начать выдачу.
    if payment.status != Payment.STATUS_PAID:
        if raw in PAID_STATUSES:
            payment.status = Payment.STATUS_PAID
            payment.paid_at = timezone.now()
            logger.info(
                "Платёж оплачен: ext=%s uid=%s %s ₽ phone=%s",
                payment.external_payment_id, payment.payment_uid,
                payment.amount_rub, mask_phone(payment.phone),
            )
        elif raw in FAILED_STATUSES:
            payment.status = Payment.STATUS_FAILED
    payment.save()
    return payment


def refresh_payment(client: AlfabitClient, payment: Payment) -> Payment:
    """Спросить alfabit о платеже и записать ответ. Бросает AlfabitError."""
    return apply_payment_state(payment, client.get_checkout_payment(payment.payment_uid))


def watch_kyc(client: AlfabitClient) -> None:
    """Досмотреть заявки KYC до approved/rejected. Зовёт `worker`.

    У бота этот реестр жил в памяти (`KycWatcher`) и умирал при рестарте. Разбор
    16.08.2026: плательщик одобрен 14.08 вечером, бот молчал двое суток, клиент
    считал, что верификация зависла.
    """
    now = timezone.now()
    for payer in Payer.objects.filter(watch_since__isnull=False):
        if now - payer.watch_since > KYC_WATCH_MAX_AGE:
            logger.warning(
                "kyc watch: заявка phone=%s не закрылась за %d ч — снимаем с "
                "наблюдения, разбирайте руками",
                mask_phone(payer.phone), KYC_WATCH_MAX_AGE.total_seconds() // 3600,
            )
            payer.watch_since = None
            payer.save(update_fields=["watch_since", "updated_at"])
            continue
        try:
            refresh_payer(client, payer.phone, user_id=None, event="watch")
        except AlfabitError as exc:
            # Сеть отвалилась — заявку не снимаем, придём на следующем круге.
            logger.warning("kyc watch: phone=%s: %s", mask_phone(payer.phone), exc)


def watch_payments(client: AlfabitClient) -> None:
    """Досмотреть неоплаченные платежи. Зовёт `worker`: человек мог закрыть
    вкладку сразу после перевода — кнопки «Я оплатил» на сайте нет."""
    since = timezone.now() - PAYMENT_WATCH_MAX_AGE
    pending = Payment.objects.filter(
        status=Payment.STATUS_CREATED, created_at__gte=since
    ).exclude(payment_uid="")
    for payment in pending:
        try:
            refresh_payment(client, payment)
        except AlfabitError as exc:
            logger.warning("payment watch: ext=%s: %s", payment.external_payment_id, exc)
