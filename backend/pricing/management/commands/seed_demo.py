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

from catalog.models import Brand, Product
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

        for name, sort, is_final in SUPPLY_STATUSES:
            SupplyStatus.objects.update_or_create(
                name=name, defaults={"sort": sort, "is_final": is_final}
            )

        if not Product.objects.exists():
            brand, _ = Brand.objects.get_or_create(name="Kayo", defaults={"sort": 10})
            Product.objects.create(
                brand=brand, model="K6-R 250", color="синий",
                price=Decimal("389000"), in_stock=True,
                description="Демо-позиция, заведена командой seed_demo. Удалите, "
                            "когда появится настоящий каталог.",
            )

        self.stdout.write(self.style.SUCCESS(
            f"Готово: источников {RateSource.objects.count()}, "
            f"способов оплаты {PaymentMethod.objects.count()}, "
            f"наценок {MarkupRule.objects.count()}, "
            f"статусов поставки {SupplyStatus.objects.count()}."
        ))
