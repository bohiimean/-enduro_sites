"""Котировки и расчёт витрины.

Две половины одной задачи:

* `fetch_quotes()` — фоновая, ходит в сервис курсов и складывает сырые
  котировки в БД. Вызывается только из `worker`: в запросе пользователя за
  границу мы не ходим (CLAUDE.md, «География размещения»).
* `build_showcase()` — синхронная, считает цену юаня по наценкам из БД.
  Именно она источник истины по цене — на неё же перейдёт бот на этапе 7.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import MarkupRule, PaymentMethod, PricingSettings, RateQuote, RateSource

logger = logging.getLogger(__name__)

_TIMEOUT = 15


class RateServiceError(RuntimeError):
    pass


def fetch_quotes() -> int:
    """Забрать котировки из сервиса курсов. Возвращает число новых записей."""
    if not settings.RATE_SERVICE_URL:
        logger.warning("RATE_SERVICE_URL не задан — котировки не обновляются")
        return 0

    url = settings.RATE_SERVICE_URL.rstrip("/") + "/rates"
    headers = {"Authorization": f"Bearer {settings.RATE_SERVICE_TOKEN}"}
    try:
        response = requests.get(url, headers=headers, timeout=_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        # Канал идёт через границу и рвётся. Это не авария: в БД лежит
        # предыдущее значение, и витрина покажет его с пометкой времени.
        raise RateServiceError(f"{type(exc).__name__}: {exc}") from exc

    created = 0
    for code, item in payload.items():
        value = (item or {}).get("value")
        fetched_raw = (item or {}).get("fetched_at")
        if value is None or not fetched_raw:
            # Источник включён, но ещё не прогрелся или падает. Прежнюю
            # котировку не трогаем.
            logger.info("Источник %s пуст — пропускаем", code)
            continue

        source = RateSource.objects.filter(code=code).first()
        if source is None:
            logger.warning("Сервис курсов отдал незнакомый источник %r — пропускаем", code)
            continue

        fetched_at = parse_datetime(fetched_raw)
        if fetched_at is None:
            logger.warning("Источник %s: не разобрали время %r", code, fetched_raw)
            continue

        # Идемпотентность: сервис отдаёт одно и то же значение, пока не
        # обновится, а `worker` может прийти чаще. Дубли отсекает уникальность
        # по (источник, время получения).
        _, is_new = RateQuote.objects.get_or_create(
            source=source, fetched_at=fetched_at, defaults={"value": Decimal(str(value))}
        )
        created += int(is_new)

    logger.info("Котировки обновлены: новых записей %d", created)
    return created


@dataclass
class Tier:
    label: str
    threshold_rub: Decimal | None
    price_per_cny: Decimal


@dataclass
class MethodPrice:
    code: str
    title: str
    subtitle: str
    note: str
    source_code: str
    available: bool
    rate: Decimal | None = None
    fetched_at: datetime | None = None
    is_stale: bool = False
    tiers: list[Tier] = field(default_factory=list)


@dataclass
class Showcase:
    divisor: Decimal
    generated_at: datetime
    methods: list[MethodPrice]


def _latest_quotes() -> dict[int, RateQuote]:
    """Последняя котировка по каждому источнику, одним проходом."""
    latest: dict[int, RateQuote] = {}
    for quote in RateQuote.objects.order_by("source_id", "-fetched_at").select_related("source"):
        latest.setdefault(quote.source_id, quote)
    return latest


def build_showcase(now: datetime | None = None) -> Showcase:
    """Витрина: цена юаня по каждому способу оплаты и тарифному уровню.

    Цена = наценка, применённая к сырому курсу, делённая на делитель юаня.
    Формула одна на оба типа наценки — различается только `apply()`:
        коэффициент:      (курс × 1.045) / 6.63
        прибавка в ₽:     (курс + 2.6)   / 6.63

    Округление до копейки — `quantize(Decimal("0.01"))` с округлением по
    умолчанию, ровно как в боте (`services/yuan.py`), чтобы цифры совпадали.
    """
    now = now or timezone.now()
    config = PricingSettings.load()
    divisor = config.cny_divisor
    stale_after = timedelta(minutes=config.stale_after_minutes)
    latest = _latest_quotes()
    # Окна действия заданы в московском времени — по нему живёт бизнес.
    local_now = timezone.localtime(now)

    methods: list[MethodPrice] = []
    queryset = (
        PaymentMethod.objects.filter(is_active=True)
        .select_related("source")
        .prefetch_related("markups")
        .order_by("sort", "id")
    )

    for method in queryset:
        price = MethodPrice(
            code=method.code,
            title=method.title,
            subtitle=method.subtitle,
            note=method.note,
            source_code=method.source.code,
            available=False,
        )
        quote = latest.get(method.source_id)
        if quote is None:
            # Источник ни разу не отдался. Способ показываем, но без цены —
            # молча прятать строку хуже, чем честно сказать «нет курса».
            logger.info("Способ %s: котировки нет", method.code)
            methods.append(price)
            continue

        price.available = True
        price.rate = quote.value
        price.fetched_at = quote.fetched_at
        price.is_stale = (now - quote.fetched_at) > stale_after

        for rule in method.markups.all():
            if not rule.applies_at(local_now):
                continue
            price.tiers.append(
                Tier(
                    label=rule.label,
                    threshold_rub=rule.threshold_rub,
                    price_per_cny=(rule.apply(quote.value) / divisor).quantize(Decimal("0.01")),
                )
            )
        price.tiers.sort(key=lambda tier: (tier.threshold_rub or Decimal(0)))
        methods.append(price)

    return Showcase(divisor=divisor, generated_at=now, methods=methods)
