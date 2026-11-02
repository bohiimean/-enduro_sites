"""Дополнительный набор для ручного тестирования локального сайта."""
import secrets
import uuid
from datetime import timedelta
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from catalog.models import Brand, Goods, GoodsCategory, Product
from orders.models import Order, PurchaseRequest, SupplyStatus
from orders.request_services import submit_request

EMAIL = "buyer.demo@example.test"
NAME = "Демо Клиент"
PHONE = "+70000000101"
DESCRIPTION = "Тестовая позиция для проверки сайта. Характеристики и цена условные. Создана командой seed_test_data."

BIKES = [
    ("atlas-250", {"model": "Atlas 250", "powertrain": "ice_4t", "stock_qty": 3, "price_cny": 15500,
                   "stock_price_rub": 245000, "displacement_cc": 250, "power_hp": 27, "weight_kg": 112}),
    ("trail-250-2t", {"model": "Trail 250 2T", "powertrain": "ice_2t", "stock_qty": 1, "price_cny": 22000,
                      "stock_price_rub": 315000, "displacement_cc": 250, "power_hp": 38, "weight_kg": 104}),
    ("volt-x", {"model": "Volt X", "powertrain": "electric", "price_cny": 28000,
                "power_kw": 18, "battery_voltage_v": 72, "battery_capacity_ah": 60, "range_km": 110}),
    ("mini-e", {"model": "Mini E", "powertrain": "electric", "stock_qty": 4, "is_orderable": False,
                "stock_price_rub": 98000, "power_kw": 6, "battery_voltage_v": 60, "battery_capacity_ah": 30, "range_km": 65}),
    ("expedition-450", {"model": "Expedition 450", "powertrain": "ice_4t", "displacement_cc": 450,
                        "power_hp": 42, "tagline": "Демо · Под заказ, цена по запросу"}),
    ("prototype", {"model": "Prototype (черновик)", "powertrain": "electric", "is_published": False,
                   "stock_qty": 1, "stock_price_rub": 111000, "power_kw": 12}),
]
GOODS = [
    ("wall-battery-5", "Настенный аккумулятор 5 кВт·ч", "Энергия для дома", "stock", 95000,
     [("Ёмкость", "5 кВт·ч"), ("Напряжение", "51,2 В"), ("Тип ячеек", "LiFePO₄"), ("Гарантия", "3 года")]),
    ("home-battery-10", "Домашний аккумулятор 10 кВт·ч", "Энергия для дома", "order", 185000,
     [("Ёмкость", "10 кВт·ч"), ("Напряжение", "51,2 В"), ("Циклы", "6000"), ("Вес", "95 кг")]),
    ("inverter-5", "Гибридный инвертор 5 кВт", "Энергия для дома", "stock", 49000,
     [("Мощность", "5 кВт"), ("Фазы", "1"), ("КПД", "97 %")]),
    ("storage-20", "Накопитель энергии 20 кВт·ч", "Энергия для дома", "order", None,
     [("Ёмкость", "20 кВт·ч"), ("Установка", "напольная"), ("Модули", "4 × 5 кВт·ч")]),
    ("helmet", "Эндуро-шлем", "Экипировка", "stock", 12500,
     [("Размеры", "M, L, XL"), ("Материал", "композит"), ("Вес", "1350 г")]),
    ("guards", "Защита рук", "Аксессуары", "stock", 4500,
     [("Крепление", "22 мм"), ("Материал", "алюминий и пластик"), ("Комплект", "левая и правая")]),
    ("draft-charger", "Зарядное устройство (черновик)", "Аксессуары", "order", 8000,
     [("Мощность", "1,5 кВт")]),
]


def demo_image(label, kind, variant):
    """Явно обозначенная тестовая иллюстрация для проверки галерей."""
    image = Image.new("RGB", (1000, 650), "#f3f4f6")
    draw = ImageDraw.Draw(image)
    accent = "#f97316" if variant == 0 else "#2563eb"
    ink = "#1f2937"
    if kind == "bike":
        for x in (260, 720):
            draw.ellipse((x-92, 335, x+92, 519), outline=ink, width=18)
        draw.line([(260, 427), (420, 285), (560, 427), (260, 427), (420, 285), (670, 265), (720, 427)], fill=ink, width=15)
        draw.polygon([(340, 265), (550, 245), (590, 300), (410, 330)], fill=accent)
        draw.line([(655, 225), (706, 218)], fill=ink, width=15)
        draw.rounded_rectangle((338, 238, 516, 264), radius=10, fill=ink)
    else:
        draw.rounded_rectangle((335, 160, 665, 510), radius=28, fill="white", outline=ink, width=8)
        draw.rounded_rectangle((385, 210, 615, 278), radius=12, fill=accent)
        for y in (330, 365, 400, 435):
            draw.line((395, y, 605, y), fill="#cbd5e1", width=8)
        draw.ellipse((475, 295, 500, 320), fill="#22c55e")
    draw.text((45, 38), "DEMO", fill=accent, font=ImageFont.load_default(size=36))
    draw.text((45, 580), label.upper().replace("-", " "), fill=ink, font=ImageFont.load_default(size=27))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def photos(product, slug, kind):
    if product.photos.exists():
        return
    for variant in (0, 1):
        path = f"demo-test-data/{kind}-{slug}-{variant}.png"
        if not default_storage.exists(path):
            path = default_storage.save(path, ContentFile(demo_image(slug, kind, variant)))
        product.photos.create(image=path, sort=variant)


class Command(BaseCommand):
    help = "Добавляет тестовые товары, клиента, заявки и заказы только при DEBUG=True; существующие записи не изменяет"

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Тестовые данные разрешены только в локальном окружении с DEBUG=True.")
        existing = User.objects.filter(email=EMAIL).first()
        if existing and (existing.full_name != NAME or existing.is_staff or existing.is_superuser):
            raise CommandError("Адрес демо-клиента уже занят другой учётной записью.")
        password = None
        if existing:
            customer = existing
        else:
            password = secrets.token_urlsafe(15)
            customer = User.objects.create_user(email=EMAIL, password=password, full_name=NAME)
            EmailAddress.objects.create(user=customer, email=EMAIL, verified=True, primary=True)

        brand, _ = Brand.objects.get_or_create(name="DEMO", defaults={"slug": "demo-test-brand"})
        bikes = {}
        for slug, fields in BIKES:
            defaults = {"brand": brand, "model_year": 2026, "tagline": "Демо · Тестовая позиция", "description": DESCRIPTION,
                        "lead_time": "30–45 дней", "colors": "оранжевый, чёрный", **fields}
            product, created = Product.objects.get_or_create(slug=f"demo-test-{slug}", defaults=defaults)
            if created:
                product.full_clean()
                photos(product, slug, "bike")
                product.extra_specs.create(name="Назначение", value="Для тестирования сайта", sort=0)
            bikes[slug] = product

        goods = {}
        for slug, title, category_name, availability, price, specs in GOODS:
            category, _ = GoodsCategory.objects.get_or_create(name=f"Демо · {category_name}")
            product, created = Goods.objects.get_or_create(slug=f"demo-test-{slug}", defaults={
                "title": f"DEMO · {title}", "category": category, "availability": availability,
                "price_rub": price, "tagline": "Демо · Тестовая позиция", "description": DESCRIPTION,
                "is_published": slug != "draft-charger", "lead_time": "30–45 дней" if availability == "order" else "",
            })
            if created:
                product.full_clean()
                photos(product, slug, "goods")
                for order, (name, value) in enumerate(specs):
                    product.specs.create(name=name, value=value, sort=order)
            goods[slug] = product

        scenarios = [
            ("new", [("bike", bikes["atlas-250"], "stock", 1), ("goods", goods["home-battery-10"], "order", 1)]),
            ("in_progress", [("bike", bikes["volt-x"], "order", 1), ("goods", goods["helmet"], "stock", 2)]),
            ("agreed", [("bike", bikes["mini-e"], "stock", 1), ("goods", goods["inverter-5"], "stock", 1)]),
            ("cancelled", [("goods", goods["storage-20"], "order", 1)]),
        ]
        for days, (status, lines) in enumerate(scenarios):
            key = uuid.uuid5(uuid.NAMESPACE_URL, f"demo-test-data:{EMAIL}:{status}")
            if PurchaseRequest.objects.filter(user=customer, submission_key=key).exists():
                continue
            request, _ = submit_request(customer, {
                "submission_key": key, "name": NAME, "phone": PHONE,
                "items": [{"kind": kind, "product_id": product.pk, "offer": offer, "quantity": qty} for kind, product, offer, qty in lines],
            })
            PurchaseRequest.objects.filter(pk=request.pk).update(
                status=status, manager_note=f"Демо-заявка: {status}. Заметка видна только менеджеру.",
                created_at=timezone.now() - timedelta(days=days),
            )

        for days, (name, final, model, paid) in enumerate([
            ("В пути", False, "atlas-250", 100000),
            ("На складе в Москве", False, "trail-250-2t", 315000),
            ("Выдан", True, "mini-e", 98000),
        ], start=1):
            status, _ = SupplyStatus.objects.get_or_create(name=name, defaults={"is_final": final, "sort": days * 10})
            Order.objects.get_or_create(external_key=f"demo-test-data:{model}", defaults={
                "user": customer, "phone": PHONE, "full_name": NAME, "product": bikes[model],
                "product_title": bikes[model].title, "color": "оранжевый", "city": "Москва", "quantity": 1,
                "price": bikes[model].stock_price_rub, "paid": paid, "supply_status": status,
                "ordered_at": timezone.localdate() - timedelta(days=days * 7), "comment": "Демо-заказ для тестирования.",
            })

        self.stdout.write(self.style.SUCCESS("Готово: 6 демо-байков, 7 других товаров, 4 заявки и 3 заказа."))
        self.stdout.write(f"Демо-клиент: {EMAIL}")
        self.stdout.write(f"Пароль: {password}" if password else "Демо-клиент уже существует: пароль не изменён.")
        self.stdout.write("Доступ в админку не выдавался. Существующие данные не изменялись.")
