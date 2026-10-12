"""Цены каталога: «под заказ» и «в наличии» — от цены завода в юанях.

    цена = (юани × цена юаня + доставка) × (1 + наценка / 100), вверх до шага

Формула одна на обе цены, различается только наценка. Ручная цена «в
наличии» её отменяет: вписанную менеджером цифру курс не трогает.

Цена юаня — ровно та цифра, что на странице курса: способ оплаты из настроек
каталога, уровень без порога суммы (`build_showcase`). Человек может сам
перемножить юани на курс со страницы и получить ту же сумму до наценки.

Округление только вверх: вниз оно съедало бы наценку.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, Decimal

from django.utils import timezone

from pricing.services import build_showcase

from .models import CatalogSettings, Product

# Сервис курсов ходит через границу и может отставать часами — прятать цены
# после каждого сбоя нельзя, каталог пустел бы на ровном месте. Но цену байка
# по курсу недельной давности показывать тоже нельзя: после суток — «цена по
# запросу».
RATE_MAX_AGE = timedelta(hours=24)


@dataclass(frozen=True)
class CatalogRate:
    price_per_cny: Decimal
    fetched_at: datetime


@dataclass(frozen=True)
class StockOffer:
    qty: int
    price_rub: Decimal | None  # None — цена по запросу


@dataclass(frozen=True)
class OrderOffer:
    price_rub: Decimal | None  # None — цена по запросу
    lead_time: str


@dataclass(frozen=True)
class Offers:
    stock: StockOffer | None  # None — нет в наличии
    order: OrderOffer | None  # None — предзаказ не принимаем
    rate: CatalogRate | None


def current_rate(config: CatalogSettings, now: datetime | None = None) -> CatalogRate | None:
    """Цена юаня для каталога или None, если считать не по чему."""
    now = now or timezone.now()
    if config.rate_method_id is None:
        return None
    code = config.rate_method.code
    method = next((m for m in build_showcase(now).methods if m.code == code), None)
    if method is None or not method.available:
        return None
    if now - method.fetched_at > RATE_MAX_AGE:
        return None
    base = next((tier for tier in method.tiers if tier.threshold_rub is None), None)
    if base is None:
        return None
    return CatalogRate(price_per_cny=base.price_per_cny, fetched_at=method.fetched_at)


def ceil_to(amount: Decimal, step: int) -> Decimal:
    return (amount / step).to_integral_value(rounding=ROUND_CEILING) * step


def price_from_cny(
    price_cny: Decimal, delivery_rub: Decimal, markup_percent: Decimal,
    price_per_cny: Decimal, step: int,
) -> Decimal:
    raw = (price_cny * price_per_cny + delivery_rub) * (1 + markup_percent / Decimal(100))
    return ceil_to(raw, step)


def offers(product: Product, config: CatalogSettings, rate: CatalogRate | None) -> Offers:
    delivery = product.delivery_rub if product.delivery_rub is not None else config.delivery_rub

    def from_cny(markup_percent: Decimal) -> Decimal | None:
        if product.price_cny is None or rate is None:
            return None
        return price_from_cny(
            product.price_cny, delivery, markup_percent, rate.price_per_cny, config.round_to_rub
        )

    stock = None
    if product.stock_qty > 0:
        price = product.stock_price_rub
        if price is None:
            price = from_cny(config.stock_markup_percent)
        stock = StockOffer(qty=product.stock_qty, price_rub=price)

    order = None
    if product.is_orderable:
        order = OrderOffer(
            price_rub=from_cny(config.order_markup_percent),
            lead_time=product.lead_time or config.lead_time,
        )

    return Offers(stock=stock, order=order, rate=rate)
