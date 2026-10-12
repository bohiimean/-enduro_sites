"""Справочники и демо-данные.

Наценки заводятся **ровно те, по которым считает прод бота сегодня**, включая
окна действия — то есть без них: в `bot/services/usd_markup.py` проверки
времени нет, уровни отдаются в любой час буднего дня. Текст бота при этом
обещает «VIP курс с 12:30 до 16:00». Это расхождение зафиксировано в CLAUDE.md
как открытый вопрос, и заполнять окно здесь наугад нельзя — данные должны
совпадать с тем, что происходит в проде. Когда клиент подтвердит окно, оно
проставляется в админке в полях «действует с/до», код менять не нужно.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Brand, CatalogSettings, Product
from orders.models import SupplyStatus
from pricing.models import MarkupRule, PaymentMethod, PricingSettings, RateSource

SOURCES = [
    (RateSource.CODE_RAPIRA, "Rapira USDT/RUB", "api.rapira.net, пара USDT/RUB, поле close"),
    (RateSource.CODE_INVESTING, "Investing USD/RUB", "скрап investing.com, 2–3 минуты на вызов"),
    (RateSource.CODE_ALFABIT, "Alfabit витрина USDT/RUB",
     "курс конвертера × комиссия метода SBPRUB, комиссия читается на лету"),
]

METHODS = [
    (PaymentMethod.CODE_QR, "QR-оплата", RateSource.CODE_RAPIRA, 10, ""),
    (PaymentMethod.CODE_QR_KYC, "QR + KYC", RateSource.CODE_ALFABIT, 20,
     "Верификация по фото паспорта, 18+. Данные при регистрации должны совпадать "
     "с данными отправителя средств в банке. Может не работать с Альфа-Банком и Озоном."),
    (PaymentMethod.CODE_CASH_MOSCOW, "Наличные в Москве", RateSource.CODE_INVESTING, 30,
     "Плюс дистанционное снятие по QR с вашего банка."),
]

# (способ, подпись, тип, значение, порог, дни недели, порядок)
MARKUPS = [
    (PaymentMethod.CODE_QR, "Стандарт", MarkupRule.KIND_MULTIPLIER, "1.045", None, "", 10),
    (PaymentMethod.CODE_QR_KYC, "Стандарт", MarkupRule.KIND_MULTIPLIER, "1.0175", None, "", 10),
    # Наличные: прибавка в рублях к курсу USD/RUB, будни и выходные различаются.
    (PaymentMethod.CODE_CASH_MOSCOW, "Стандарт", MarkupRule.KIND_RUB_ADD, "2.6", None, "12345", 10),
    (PaymentMethod.CODE_CASH_MOSCOW, "от 300 000 ₽", MarkupRule.KIND_RUB_ADD, "2.1", "300000", "12345", 20),
    (PaymentMethod.CODE_CASH_MOSCOW, "от 500 000 ₽", MarkupRule.KIND_RUB_ADD, "1.7", "500000", "12345", 30),
    (PaymentMethod.CODE_CASH_MOSCOW, "от 1 000 000 ₽", MarkupRule.KIND_RUB_ADD, "1.5", "1000000", "12345", 40),
    (PaymentMethod.CODE_CASH_MOSCOW, "Стандарт", MarkupRule.KIND_RUB_ADD, "2.7", None, "67", 50),
    (PaymentMethod.CODE_CASH_MOSCOW, "от 300 000 ₽", MarkupRule.KIND_RUB_ADD, "2.5", "300000", "67", 60),
    (PaymentMethod.CODE_CASH_MOSCOW, "от 500 000 ₽", MarkupRule.KIND_RUB_ADD, "2.1", "500000", "67", 70),
]

# По карточке на ДВС и электро, чтобы были видны оба набора характеристик.
# Характеристики — из открытых спецификаций, цена завода условная.
DEMO_NOTE = ("Демо-позиция, заведена командой seed_demo: цена условная. "
             "Удалите, когда появится настоящий каталог.")
DEMO_BIKES = [
    ("STN", {
        "model": "G9 Pro", "model_year": 2026, "powertrain": Product.ICE_4T,
        "tagline": "Эндуро 300 см³ на каждый день", "description": DEMO_NOTE,
        "price_cny": Decimal("15000"), "stock_qty": 2,
        "displacement_cc": 300, "power_hp": Decimal("30"), "transmission": "6-ступенчатая",
    }),
    ("Surron", {
        "model": "Ultra Bee HP", "model_year": 2026, "powertrain": Product.ELECTRIC,
        "tagline": "Электро-эндуро, 24,5 кВт в режиме Turbo", "description": DEMO_NOTE,
        "price_cny": Decimal("35000"),
        "power_kw": Decimal("24.5"), "battery_voltage_v": 74,
        "battery_capacity_ah": Decimal("60"), "range_km": 115, "max_speed_kmh": 95,
    }),
]

SUPPLY_STATUSES = [
    ("Новый", 10, False),
    ("Оплачен", 20, False),
    ("В пути", 30, False),
    ("На складе в Москве", 40, False),
    ("Выдан", 50, True),
    ("Отменён", 60, True),
]


class Command(BaseCommand):
    help = "Заполняет справочники курса, статусы поставки и демо-каталог"

    @transaction.atomic
    def handle(self, *args, **options):
        for code, title, description in SOURCES:
            RateSource.objects.update_or_create(
                code=code, defaults={"title": title, "description": description}
            )

        for code, title, source_code, sort, note in METHODS:
            PaymentMethod.objects.update_or_create(
                code=code,
                defaults={
                    "title": title,
                    "note": note,
                    "sort": sort,
                    "source": RateSource.objects.get(code=source_code),
                },
            )

        for method_code, label, kind, value, threshold, weekdays, sort in MARKUPS:
            MarkupRule.objects.update_or_create(
                method=PaymentMethod.objects.get(code=method_code),
                label=label,
                weekdays=weekdays,
                defaults={
                    "kind": kind,
                    "value": Decimal(value),
                    "threshold_rub": Decimal(threshold) if threshold else None,
                    "sort": sort,
                },
            )

        PricingSettings.load()

        # Каталог считает цены по курсу QR-оплаты — той же цифре, что в шапке
        # страницы курса. Выбор, сделанный в админке, не перетираем.
        catalog = CatalogSettings.load()
        if catalog.rate_method_id is None:
            catalog.rate_method = PaymentMethod.objects.get(code=PaymentMethod.CODE_QR)
            catalog.save()

        for name, sort, is_final in SUPPLY_STATUSES:
            SupplyStatus.objects.update_or_create(
                name=name, defaults={"sort": sort, "is_final": is_final}
            )

        if not Product.objects.exists():
            for brand_name, fields in DEMO_BIKES:
                brand, _ = Brand.objects.get_or_create(name=brand_name)
                Product.objects.create(brand=brand, **fields)

        self.stdout.write(self.style.SUCCESS(
            f"Готово: источников {RateSource.objects.count()}, "
            f"способов оплаты {PaymentMethod.objects.count()}, "
            f"наценок {MarkupRule.objects.count()}, "
            f"статусов поставки {SupplyStatus.objects.count()}."
        ))
