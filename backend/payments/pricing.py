"""Цена юаня для платежа — по свежему курсу, а не по витрине из БД.

Витрина (`pricing.build_showcase`) берёт котировку, которую `worker` кладёт
раз в 20 минут. Для страницы курса этого хватает, а для суммы, которую человек
заплатит, — нет: бот перед созданием платежа берёт курс alfabit не старше трёх
минут, и сайт должен считать не хуже (решено 27.09.2026).

Правило «в запросе пользователя сайт за границу не ходит» здесь не нарушается:
оно про `rate-service` и скрап investing. В alfabit мы в этом же запросе идём
создавать платёж, то есть курс оттуда же — это тот же адресат и та же
доступность.

Что откуда:
    курс витрины alfabit  — считается здесь, так же как в `rate-service`
                            (`app/providers/alfabit.py`, там обоснование):
                            rate_effective × (1 + комиссия метода SBPRUB / 100);
    наценка и делитель    — из БД, те же, что на витрине (правятся в админке).

Если alfabit курс не отдал, берётся последняя котировка из БД, но только
свежая (`STORED_MAX_AGE`). Старше — платёж не создаём: зафиксировать человеку
цену двухчасовой давности хуже, чем честно сказать «попробуйте позже».
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from pricing.models import MarkupRule, PaymentMethod, PricingSettings, RateQuote, RateSource

from .alfabit import AlfabitError, get_client

logger = logging.getLogger(__name__)

# Публичный API сайта alfabit — тот, которым пользуется виджет «Купить USDT».
# Ни ключа, ни подписи не требует. Префикс именно такой: под /api/v1 (без
# /wallet-web) отдаётся HTML одностраничника, а не JSON. Эндпоинты
# недокументированы и могут смениться — запасные пути ниже.
_PUBLIC_PREFIX = "/wallet-web/api/v1"
_QR_METHOD_CODE = "SBPRUB"
_TIMEOUT = 10

# Последняя успешно прочитанная комиссия метода. В кеше (таблица PostgreSQL),
# а не в памяти процесса: переживает рестарт и общая для всех воркеров. Нужна,
# если список банков временно пуст — считать без комиссии нельзя, это тихо
# уронило бы цену на 1.8%.
_FEE_CACHE_KEY = "alfabit:last_fee_percent"

STORED_MAX_AGE = timedelta(minutes=20)


class PriceUnavailable(RuntimeError):
    """Курса для платежа нет: ни свежего, ни достаточно свежего в БД."""


@dataclass(frozen=True)
class PaymentPrice:
    rate: Decimal            # курс витрины alfabit, USDT/RUB, без нашей наценки
    price_per_cny: Decimal   # цена юаня с наценкой, ₽
    fetched_at: datetime
    fresh: bool              # True — прямо сейчас от alfabit, False — из БД

    def rub_for(self, amount_cny: Decimal) -> Decimal:
        return (amount_cny * self.price_per_cny).quantize(Decimal("0.01"))


def _public_get(path: str, **params) -> dict | list:
    base = settings.ALFABIT_BASE_URL.rstrip("/") + _PUBLIC_PREFIX
    response = requests.get(base + path, params=params or None, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _base_rate() -> Decimal:
    """rate_effective — курс конвертера со спредом, без комиссии метода."""
    try:
        data = _public_get(
            "/public/fiat-converter/rate",
            crypto_symbol="USDT",
            fiat_code="RUB",
            direction=settings.ALFABIT_RATE_DIRECTION,
        )
        return Decimal(str(data["rate_effective"]))
    except (requests.RequestException, ValueError, KeyError, TypeError):
        # Публичный эндпоинт лёг — тот же курс доступен по подписанному
        # integration API (проверено: цифра совпадает до знака).
        client = get_client()
        if client is None:
            raise
        logger.warning("Alfabit: публичный курс недоступен, берём подписанный", exc_info=True)
        return client.converter_fiat_rate(direction=settings.ALFABIT_RATE_DIRECTION)


def _fee_percent() -> Decimal:
    """Комиссия метода оплаты QR (deposit_fee_percent), в процентах."""
    try:
        payload = _public_get("/public/buy-sell/banks/RUB")
        banks = payload["data"] if isinstance(payload, dict) else payload
        for bank in banks:
            if bank.get("bestchange_code") == _QR_METHOD_CODE:
                fee = Decimal(str(bank["deposit_fee_percent"]))
                cache.set(_FEE_CACHE_KEY, str(fee), timeout=None)
                return fee
        raise LookupError(f"метод {_QR_METHOD_CODE} не найден в списке банков")
    except (requests.RequestException, ValueError, KeyError, TypeError, LookupError):
        last = cache.get(_FEE_CACHE_KEY)
        if last is not None:
            logger.warning("Alfabit: список банков недоступен, комиссия %s%% из кеша", last)
            return Decimal(last)
        if settings.ALFABIT_FEE_PERCENT_FALLBACK is not None:
            # Аварийный клапан оператора, по умолчанию выключен: зашитая
            # комиссия перестаёт ехать за кабинетом alfabit.
            logger.warning(
                "Alfabit: комиссия недоступна, берём заданную оператором %s%%",
                settings.ALFABIT_FEE_PERCENT_FALLBACK,
            )
            return settings.ALFABIT_FEE_PERCENT_FALLBACK
        raise


def _fresh_showcase_rate() -> Decimal:
    base = _base_rate()
    fee = _fee_percent()
    return base * (1 + fee / 100)


def _rule_for(method: PaymentMethod, moment: datetime, rub: Decimal | None) -> MarkupRule | None:
    """Действующий уровень наценки. С порогом суммы — самый высокий из
    достигнутых; без суммы — базовый (без порога)."""
    rules = [r for r in method.markups.all() if r.applies_at(moment)]
    reached = [
        r for r in rules
        if r.threshold_rub is None or (rub is not None and rub >= r.threshold_rub)
    ]
    if not reached:
        return None
    return max(reached, key=lambda r: r.threshold_rub or Decimal(0))


def payment_price(amount_cny: Decimal | None = None) -> PaymentPrice:
    """Цена юаня для способа «QR + KYC» прямо сейчас."""
    now = timezone.now()
    method = (
        PaymentMethod.objects.filter(code=PaymentMethod.CODE_QR_KYC, is_active=True)
        .prefetch_related("markups")
        .first()
    )
    if method is None:
        raise PriceUnavailable("способ оплаты «QR + KYC» выключен в админке")

    try:
        rate, fetched_at, fresh = _fresh_showcase_rate(), now, True
        # Заодно обновляем витрину: котировка свежая, и странице курса она тоже
        # пригодится.
        source = RateSource.objects.filter(code=RateSource.CODE_ALFABIT).first()
        if source is not None:
            RateQuote.objects.get_or_create(
                source=source, fetched_at=now, defaults={"value": rate.quantize(Decimal("0.000001"))}
            )
    except (requests.RequestException, ValueError, KeyError, TypeError, LookupError, AlfabitError):
        logger.warning("Alfabit: свежий курс не получен, смотрим БД", exc_info=True)
        quote = (
            RateQuote.objects.filter(source__code=RateSource.CODE_ALFABIT)
            .order_by("-fetched_at")
            .first()
        )
        if quote is None or now - quote.fetched_at > STORED_MAX_AGE:
            raise PriceUnavailable("курс alfabit недоступен") from None
        rate, fetched_at, fresh = quote.value, quote.fetched_at, False

    divisor = PricingSettings.load().cny_divisor
    local_now = timezone.localtime(now)

    base_rule = _rule_for(method, local_now, None)
    if base_rule is None:
        raise PriceUnavailable("у способа «QR + KYC» нет действующей наценки")
    rule = base_rule
    if amount_cny is not None:
        # Порог уровня задан в рублях, а рубли зависят от уровня. Считаем сумму
        # по базовому уровню и по ней выбираем итоговый — так же читается
        # таблица уровней на витрине.
        base_price = base_rule.apply(rate) / divisor
        rule = _rule_for(method, local_now, amount_cny * base_price) or base_rule

    price = (rule.apply(rate) / divisor).quantize(Decimal("0.01"))
    return PaymentPrice(rate=rate, price_per_cny=price, fetched_at=fetched_at, fresh=fresh)
