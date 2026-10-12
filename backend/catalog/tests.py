"""Каталог: две цены от курса, характеристики по типу байка, публичное API.

Ожидаемые суммы посчитаны руками по формуле, а не взяты из вывода кода:

    (юани × цена юаня + доставка) × (1 + наценка / 100), вверх до шага

Базовая обстановка — как в проде: QR-оплата на котировке Rapira с наценкой
×1.045 и делителем 6.63. Котировка 87.6 даёт цену юаня
87.6 × 1.045 / 6.63 = 13.8072… → 13,81 ₽. Байк — 30 000 ¥, доставка по
умолчанию 30 000 ₽, наценки 5% под заказ и 10% в наличии, шаг 1 000 ₽.
"""
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.models import User
from pricing.models import MarkupRule, PaymentMethod, PricingSettings, RateQuote, RateSource

from .admin import rub
from .models import Brand, CatalogSettings, Product, ProductPhoto, ProductSpec
from .pricing import StockOffer, ceil_to, current_rate, offers, price_from_cny
from .specs import fmt_number, highlights, spec_groups

D = Decimal
MSK = ZoneInfo("Europe/Moscow")
LIST_URL = "/api/v1/catalog/products/"


def make_rate(value="87.6", fetched_at=None):
    """QR-оплата с наценкой ×1.045 и котировкой 10 минут назад; каталог
    считает по ней, доставка по умолчанию 30 000 ₽."""
    source = RateSource.objects.create(code=RateSource.CODE_RAPIRA, title="Rapira")
    method = PaymentMethod.objects.create(
        code=PaymentMethod.CODE_QR, title="QR-оплата", source=source
    )
    MarkupRule.objects.create(
        method=method, label="Стандарт", kind=MarkupRule.KIND_MULTIPLIER, value=D("1.045")
    )
    RateQuote.objects.create(
        source=source, value=D(value),
        fetched_at=fetched_at or timezone.now() - timedelta(minutes=10),
    )
    PricingSettings.load()
    config = CatalogSettings.load()
    config.rate_method = method
    config.delivery_rub = D("30000")
    config.save()
    return method


def bike(brand="Surron", **fields):
    values = {"model": "Ultra Bee", "powertrain": Product.ELECTRIC, "price_cny": D("30000")}
    values.update(fields)
    brand_obj, _ = Brand.objects.get_or_create(name=brand)
    return Product.objects.create(brand=brand_obj, **values)


class PriceFormulaTests(SimpleTestCase):
    def test_formula(self):
        # (30 000 × 13,81 + 30 000) × 1,05 = 466 515 → 467 000
        self.assertEqual(
            price_from_cny(D("30000"), D("30000"), D("5"), D("13.81"), 1000), D("467000")
        )

    def test_rounding_goes_up_never_down(self):
        self.assertEqual(ceil_to(D("466001"), 1000), D("467000"))
        self.assertEqual(ceil_to(D("466999.99"), 1000), D("467000"))

    def test_exact_step_stays_put(self):
        self.assertEqual(ceil_to(D("467000"), 1000), D("467000"))

    def test_step_of_one_rouble_rounds_kopecks_up(self):
        # (30 000,5 × 13,81 + 30 000) × 1,05 = 466 522,25025 → 466 523
        self.assertEqual(
            price_from_cny(D("30000.5"), D("30000"), D("5"), D("13.81"), 1), D("466523")
        )


class OffersTests(TestCase):
    def setUp(self):
        make_rate()
        self.config = CatalogSettings.load()
        self.rate = current_rate(self.config)

    def offers(self, product):
        return offers(product, self.config, self.rate)

    def test_rate_is_the_price_from_the_rate_page(self):
        # 87,6 × 1,045 / 6,63 = 13,8072… → 13,81
        self.assertEqual(self.rate.price_per_cny, D("13.81"))

    def test_order_price(self):
        self.assertEqual(self.offers(bike()).order.price_rub, D("467000"))

    def test_stock_price_has_its_own_markup(self):
        # (30 000 × 13,81 + 30 000) × 1,10 = 488 730 → 489 000
        self.assertEqual(self.offers(bike(stock_qty=2)).stock, StockOffer(qty=2, price_rub=D("489000")))

    def test_delivery_of_the_model_replaces_the_default(self):
        # (414 300 + 50 000) × 1,05 = 487 515 → 488 000
        self.assertEqual(self.offers(bike(delivery_rub=D("50000"))).order.price_rub, D("488000"))

    def test_zero_delivery_of_the_model_is_not_replaced_by_the_default(self):
        # 414 300 × 1,05 = 435 015 → 436 000
        self.assertEqual(self.offers(bike(delivery_rub=D("0"))).order.price_rub, D("436000"))

    def test_markup_and_step_come_from_settings(self):
        self.config.order_markup_percent = D("0")
        self.config.round_to_rub = 1
        # 414 300 + 30 000 = 444 300 ровно
        self.assertEqual(self.offers(bike()).order.price_rub, D("444300"))

    def test_manual_stock_price_ignores_the_rate(self):
        product = bike(stock_qty=1, stock_price_rub=D("520000"))
        self.assertEqual(self.offers(product).stock.price_rub, D("520000"))
        self.assertEqual(offers(product, self.config, None).stock.price_rub, D("520000"))

    def test_without_yuan_price_both_are_on_request(self):
        found = self.offers(bike(price_cny=None, stock_qty=1))
        self.assertIsNone(found.stock.price_rub)
        self.assertIsNone(found.order.price_rub)

    def test_without_rate_computed_prices_are_on_request(self):
        found = offers(bike(stock_qty=1), self.config, None)
        self.assertIsNone(found.stock.price_rub)
        self.assertIsNone(found.order.price_rub)
        self.assertIsNone(found.rate)

    def test_nothing_in_stock_means_no_stock_offer(self):
        self.assertIsNone(self.offers(bike(stock_qty=0, stock_price_rub=D("520000"))).stock)

    def test_pre_order_switched_off(self):
        self.assertIsNone(self.offers(bike(is_orderable=False)).order)

    def test_lead_time_of_the_model_or_the_default(self):
        self.config.lead_time = "45–60 дней"
        self.assertEqual(self.offers(bike()).order.lead_time, "45–60 дней")
        self.assertEqual(self.offers(bike(lead_time="20 дней")).order.lead_time, "20 дней")


class CatalogRateTests(TestCase):
    def test_no_method_chosen(self):
        make_rate()
        config = CatalogSettings.load()
        config.rate_method = None
        config.save()
        self.assertIsNone(current_rate(config))

    def test_no_quote_yet(self):
        make_rate()
        RateQuote.objects.all().delete()
        self.assertIsNone(current_rate(CatalogSettings.load()))

    def test_method_switched_off_on_the_rate_page(self):
        method = make_rate()
        method.is_active = False
        method.save()
        self.assertIsNone(current_rate(CatalogSettings.load()))

    def test_method_without_base_tier(self):
        method = make_rate()
        method.markups.update(threshold_rub=D("300000"))
        self.assertIsNone(current_rate(CatalogSettings.load()))

    def test_rate_older_than_a_day_gives_no_price(self):
        now = timezone.now()
        make_rate(fetched_at=now - timedelta(hours=23))
        config = CatalogSettings.load()
        self.assertEqual(current_rate(config, now=now).price_per_cny, D("13.81"))
        self.assertIsNone(current_rate(config, now=now + timedelta(hours=2)))

    def test_base_tier_of_the_day_and_never_the_threshold_tiers(self):
        source = RateSource.objects.create(code=RateSource.CODE_INVESTING, title="Investing")
        cash = PaymentMethod.objects.create(
            code=PaymentMethod.CODE_CASH_MOSCOW, title="Наличные", source=source
        )
        for label, value, threshold, weekdays in [
            ("Стандарт", "2.6", None, "12345"),
            ("от 300 000 ₽", "2.1", D("300000"), "12345"),
            ("Стандарт", "2.7", None, "67"),
        ]:
            MarkupRule.objects.create(
                method=cash, label=label, kind=MarkupRule.KIND_RUB_ADD, value=D(value),
                threshold_rub=threshold, weekdays=weekdays,
            )
        sunday = datetime(2026, 10, 11, 23, 0, tzinfo=MSK)
        monday = datetime(2026, 10, 12, 1, 0, tzinfo=MSK)
        RateQuote.objects.create(
            source=source, value=D("86"), fetched_at=sunday - timedelta(minutes=10)
        )
        config = CatalogSettings.load()
        config.rate_method = cash
        config.save()

        # (86 + 2,7) / 6,63 = 13,3786… → 13,38 в выходные
        self.assertEqual(current_rate(config, now=sunday).price_per_cny, D("13.38"))
        # (86 + 2,6) / 6,63 = 13,3635… → 13,36 в будни; уровень «от 300 000 ₽»
        # дал бы 13,29 — в каталоге его нет
        self.assertEqual(current_rate(config, now=monday).price_per_cny, D("13.36"))


class SpecTests(TestCase):
    @staticmethod
    def flat(product):
        return [(g.title, [(i.label, i.value) for i in g.items]) for g in spec_groups(product)]

    def test_numbers_read_like_text(self):
        self.assertEqual(fmt_number(D("85.0")), "85")
        self.assertEqual(fmt_number(D("24.5")), "24,5")
        self.assertEqual(fmt_number(D("100")), "100")
        self.assertEqual(fmt_number(920), "920")

    def test_two_stroke(self):
        product = bike(
            brand="Hengjian", model="Z300 S7", powertrain=Product.ICE_2T,
            engine="Loncin 300 2T", displacement_cc=300, power_hp=D("40"), cooling="liquid",
            fuel_system="карбюратор Keihin PWK 38", transmission="6-ступенчатая",
            starter="both", fuel_tank_l=D("8.5"), max_speed_kmh=120, weight_kg=D("105"),
            seat_height_mm=950, frame="хромомолибденовая сталь", wheels="21/18",
        )
        self.assertEqual(self.flat(product), [
            ("Двигатель", [
                ("Двигатель", "Loncin 300 2T"),
                ("Тип", "2-тактный"),
                ("Объём", "300 см³"),
                ("Мощность", "40 л.с."),
                ("Охлаждение", "жидкостное"),
                ("Питание", "карбюратор Keihin PWK 38"),
                ("КПП", "6-ступенчатая"),
                ("Запуск", "электростартер и кик"),
                ("Бак", "8,5 л"),
                ("Макс. скорость", "120 км/ч"),
            ]),
            ("Ходовая часть", [("Рама", "хромомолибденовая сталь"), ("Колёса", "21/18")]),
            ("Размеры и вес", [("Вес", "105 кг"), ("Высота по седлу", "950 мм")]),
        ])
        self.assertEqual(highlights(product), ["300 см³", "2T", "40 л.с."])

    def test_four_stroke_shows_horsepower_first(self):
        product = bike(
            brand="STN", model="G9 Pro", powertrain=Product.ICE_4T,
            power_hp=D("32"), power_kw=D("23.5"), ground_clearance_mm=340,
        )
        self.assertEqual(self.flat(product), [
            ("Двигатель", [("Тип", "4-тактный"), ("Мощность", "32 л.с. (23,5 кВт)")]),
            ("Размеры и вес", [("Клиренс", "340 мм")]),
        ])
        self.assertEqual(highlights(product), ["4T", "32 л.с."])

    def test_electric(self):
        product = bike(
            engine="PMSM, средний привод", power_kw=D("24.5"), power_hp=D("33"),
            torque_nm=520, battery_voltage_v=74, battery_capacity_ah=D("60"), range_km=115,
            charge_time_h=D("2.5"), max_speed_kmh=95, weight_kg=D("85"),
            fork="USD, ход 240 мм", shock="моноамортизатор", brakes="гидравлика, 4 поршня",
        )
        ProductSpec.objects.create(product=product, name="Реверс", value="есть", sort=2)
        ProductSpec.objects.create(product=product, name="Режимы", value="Eco / Sport / Turbo", sort=1)
        self.assertEqual(self.flat(product), [
            ("Мотор и батарея", [
                ("Мотор", "PMSM, средний привод"),
                ("Мощность", "24,5 кВт (33 л.с.)"),
                ("Крутящий момент", "520 Н·м"),
                # 74 × 60 = 4 440 Вт·ч → 4,4 кВт·ч
                ("Батарея", "74 В · 60 А·ч (4,4 кВт·ч)"),
                ("Запас хода", "до 115 км"),
                ("Зарядка", "2,5 ч"),
                ("Макс. скорость", "95 км/ч"),
            ]),
            ("Ходовая часть", [
                ("Вилка", "USD, ход 240 мм"), ("Амортизатор", "моноамортизатор"),
                ("Тормоза", "гидравлика, 4 поршня"),
            ]),
            ("Размеры и вес", [("Вес", "85 кг")]),
            ("Дополнительно", [("Режимы", "Eco / Sport / Turbo"), ("Реверс", "есть")]),
        ])
        self.assertEqual(highlights(product), ["24,5 кВт", "74 В · 60 А·ч", "до 115 км"])

    def test_half_filled_battery_has_no_energy(self):
        product = bike(battery_voltage_v=74)
        self.assertEqual(self.flat(product), [("Мотор и батарея", [("Батарея", "74 В")])])
        self.assertEqual(highlights(bike(battery_capacity_ah=D("75"))), ["75 А·ч"])

    def test_power_in_one_unit_only(self):
        self.assertEqual(highlights(bike(power_hp=D("33"))), ["33 л.с."])
        engine_bike = bike(brand="STN", model="G9", powertrain=Product.ICE_4T, power_kw=D("22"))
        self.assertEqual(highlights(engine_bike), ["4T", "22 кВт"])

    def test_fields_of_the_other_type_are_not_shown(self):
        # Через админку так не сохранить (см. валидацию), но ORM пропустит.
        electric = bike(displacement_cc=300, fuel_tank_l=D("8"))
        engine_bike = bike(brand="STN", model="G9 Pro", powertrain=Product.ICE_4T,
                           battery_voltage_v=74, range_km=100)
        self.assertEqual(self.flat(electric), [])
        self.assertEqual(self.flat(engine_bike), [("Двигатель", [("Тип", "4-тактный")])])
        self.assertEqual(highlights(electric), [])


class ProductModelTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Arctic Leopard")

    def product(self, **fields):
        return Product(brand=self.brand, model="EX800", **fields)

    def test_electric_cannot_carry_engine_fields(self):
        product = self.product(powertrain=Product.ELECTRIC, displacement_cc=300, cooling="liquid")
        with self.assertRaises(ValidationError) as caught:
            product.full_clean()
        self.assertEqual(set(caught.exception.message_dict), {"displacement_cc", "cooling"})

    def test_engine_bike_cannot_carry_battery_fields(self):
        product = self.product(powertrain=Product.ICE_4T, battery_voltage_v=74, range_km=100)
        with self.assertRaises(ValidationError) as caught:
            product.full_clean()
        self.assertEqual(set(caught.exception.message_dict), {"battery_voltage_v", "range_km"})

    def test_shared_fields_suit_every_type(self):
        for powertrain in (Product.ICE_2T, Product.ICE_4T, Product.ELECTRIC):
            with self.subTest(powertrain=powertrain):
                self.product(
                    powertrain=powertrain, power_hp=D("33"), power_kw=D("24.5"),
                    weight_kg=D("85"), max_speed_kmh=95, wheels="19/16",
                ).full_clean()

    def test_type_is_required(self):
        with self.assertRaises(ValidationError) as caught:
            self.product(powertrain="").full_clean()
        self.assertEqual(set(caught.exception.message_dict), {"powertrain"})

    def test_money_cannot_be_negative(self):
        product = self.product(
            powertrain=Product.ICE_4T, price_cny=D("-1"), delivery_rub=D("-1"),
            stock_price_rub=D("-1"),
        )
        with self.assertRaises(ValidationError) as caught:
            product.full_clean()
        self.assertEqual(
            set(caught.exception.message_dict), {"price_cny", "delivery_rub", "stock_price_rub"}
        )

    def test_title_and_address_with_year(self):
        product = bike(brand="STN", model="G9 Pro", powertrain=Product.ICE_4T, model_year=2026)
        self.assertEqual(product.title, "STN G9 Pro 2026")
        self.assertEqual(str(product), "STN G9 Pro 2026")
        self.assertEqual(product.slug, "stn-g9-pro-2026")

    def test_address_is_unique_and_stable(self):
        first, second = bike(), bike()
        self.assertEqual((first.slug, second.slug), ("surron-ultra-bee", "surron-ultra-bee-2"))
        first.model = "Ultra Bee HP"
        first.save()
        self.assertEqual(first.slug, "surron-ultra-bee")

    def test_brand_address_survives_cyrillic_names(self):
        first = Brand.objects.create(name="Кайо")
        second = Brand.objects.create(name="Авантис")
        self.assertEqual((first.slug, second.slug), ("brand", "brand-2"))
        self.assertEqual(self.brand.slug, "arctic-leopard")
        # Админка присылает адрес готовым (заполняет его по названию сама).
        self.assertEqual(Brand.objects.create(name="Avantis", slug="avantis-moto").slug, "avantis-moto")
        self.assertEqual(str(self.brand), "Arctic Leopard")

    def test_names_in_admin(self):
        product = bike()
        self.assertEqual(str(ProductSpec(product=product, name="Реверс", value="есть")), "Реверс: есть")
        self.assertEqual(str(ProductPhoto(product=product)), "Фото Surron Ultra Bee")
        self.assertEqual(str(CatalogSettings.load()), "Настройки каталога")

    def test_settings_stay_a_single_row(self):
        CatalogSettings(order_markup_percent=D("7")).save()
        CatalogSettings(order_markup_percent=D("8")).save()
        self.assertEqual(CatalogSettings.objects.count(), 1)
        self.assertEqual(CatalogSettings.load().order_markup_percent, D("8"))


class CatalogApiTests(TestCase):
    """Ходим как фронтенд: анонимно, через публичные адреса."""

    def setUp(self):
        make_rate()
        config = CatalogSettings.load()
        config.lead_time = "45–60 дней"
        config.save()
        self.client = Client()

    def detail(self, product):
        return self.client.get(f"{LIST_URL}{product.slug}/")

    def slugs(self, query=""):
        return {item["slug"] for item in self.client.get(LIST_URL + query).json()["results"]}

    def test_card(self):
        product = bike(
            model_year=2026, tagline="Флагман электро-эндуро", colors="чёрный, серый",
            documents=Product.DOCS_NONE, stock_qty=2, power_kw=D("24.5"),
            battery_voltage_v=74, battery_capacity_ah=D("60"), range_km=115,
        )
        data = self.detail(product).json()
        self.assertEqual(data["title"], "Surron Ultra Bee 2026")
        self.assertEqual(data["brand"]["name"], "Surron")
        self.assertEqual((data["powertrain"], data["powertrain_label"]), ("electric", "Электро"))
        self.assertEqual(data["tagline"], "Флагман электро-эндуро")
        self.assertEqual(data["colors"], "чёрный, серый")
        self.assertEqual(data["documents_label"], "Без ПТС — для бездорожья и спорта")
        self.assertEqual(data["highlights"], ["24,5 кВт", "74 В · 60 А·ч", "до 115 км"])
        self.assertEqual(data["specs"], [{"title": "Мотор и батарея", "items": [
            {"label": "Мощность", "value": "24,5 кВт"},
            {"label": "Батарея", "value": "74 В · 60 А·ч (4,4 кВт·ч)"},
            {"label": "Запас хода", "value": "до 115 км"},
        ]}])
        self.assertEqual(data["stock"], {"qty": 2, "price_rub": "489000.00"})
        self.assertEqual(data["order"], {"price_rub": "467000.00", "lead_time": "45–60 дней"})
        self.assertEqual(data["rate"]["price_per_cny"], "13.81")
        self.assertEqual(data["photos"], [])

    def test_photo_address_does_not_depend_on_who_asks(self):
        product = bike()
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            ProductPhoto.objects.create(
                product=product, sort=1, image=SimpleUploadedFile("ub.png", b"png", "image/png")
            )
            # Так ходит Nuxt при рендере на сервере — напрямую в контейнер.
            data = self.client.get(f"{LIST_URL}{product.slug}/", HTTP_HOST="backend:8000").json()
        [photo] = data["photos"]
        self.assertRegex(photo["url"], r"^/media/catalog/\d{4}/\d{2}/ub[^/]*\.png$")

    def test_list_shows_the_same_prices(self):
        product = bike(stock_qty=1)
        [item] = self.client.get(LIST_URL).json()["results"]
        self.assertEqual(item["slug"], product.slug)
        self.assertEqual(item["stock"]["price_rub"], "489000.00")
        self.assertEqual(item["order"]["price_rub"], "467000.00")

    def test_on_request_prices_are_null(self):
        data = self.detail(bike(price_cny=None, stock_qty=1)).json()
        self.assertEqual(data["stock"], {"qty": 1, "price_rub": None})
        self.assertEqual(data["order"], {"price_rub": None, "lead_time": "45–60 дней"})

    def test_absent_offers_are_null(self):
        data = self.detail(bike(stock_qty=0, is_orderable=False)).json()
        self.assertIsNone(data["stock"])
        self.assertIsNone(data["order"])

    def test_without_rate(self):
        config = CatalogSettings.load()
        config.rate_method = None
        config.save()
        data = self.detail(bike()).json()
        self.assertIsNone(data["rate"])
        self.assertIsNone(data["order"]["price_rub"])

    def test_unpublished_is_hidden(self):
        shown, hidden = bike(), bike(is_published=False)
        self.assertEqual(self.slugs(), {shown.slug})
        self.assertEqual(self.detail(hidden).status_code, 404)

    def test_filters(self):
        engine_in_stock = bike(brand="STN", model="G9 Pro", powertrain=Product.ICE_4T,
                               stock_qty=1, is_orderable=False)
        electric = bike()
        two_stroke = bike(brand="Hengjian", model="Z300 S7", powertrain=Product.ICE_2T)
        # «Под заказ» — всё, что можно заказать, в том числе то, что есть и
        # в наличии: в наличии дороже, человек выбирает сам.
        in_stock_and_orderable = bike(brand="Arctic Leopard", model="EX800", stock_qty=1)
        neither = bike(brand="Kayo", model="K1", powertrain=Product.ICE_4T, is_orderable=False)
        everything = {engine_in_stock.slug, electric.slug, two_stroke.slug,
                      in_stock_and_orderable.slug, neither.slug}

        self.assertEqual(self.slugs("?availability=stock"),
                         {engine_in_stock.slug, in_stock_and_orderable.slug})
        self.assertEqual(self.slugs("?availability=order"),
                         {electric.slug, two_stroke.slug, in_stock_and_orderable.slug})
        self.assertEqual(self.slugs("?powertrain=ice"),
                         {engine_in_stock.slug, two_stroke.slug, neither.slug})
        self.assertEqual(self.slugs("?powertrain=electric"),
                         {electric.slug, in_stock_and_orderable.slug})
        self.assertEqual(self.slugs("?powertrain=ice&availability=order"), {two_stroke.slug})
        self.assertEqual(self.slugs("?availability=old&powertrain="), everything)

    def test_queries_do_not_grow_with_the_catalog(self):
        bike()
        with CaptureQueriesContext(connection) as one:
            self.client.get(LIST_URL)
        for n in range(4):
            product = bike(brand=f"Brand {n}", stock_qty=1)
            ProductSpec.objects.create(product=product, name="Реверс", value="есть")
        with CaptureQueriesContext(connection) as five:
            response = self.client.get(LIST_URL)
        self.assertEqual(response.json()["count"], 5)
        self.assertEqual(len(five), len(one))


class CatalogAdminTests(TestCase):
    def setUp(self):
        make_rate()
        self.client = Client()
        self.client.force_login(User.objects.create_superuser("admin@example.com", "x"))

    def page(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_pages_open(self):
        product = bike(stock_qty=1)
        for url in [
            "/admin/catalog/product/",
            "/admin/catalog/product/add/",
            f"/admin/catalog/product/{product.pk}/change/",
            "/admin/catalog/brand/",
            "/admin/catalog/catalogsettings/",
        ]:
            with self.subTest(url=url):
                self.page(url)

    def test_change_form_shows_what_the_site_shows(self):
        product = bike(stock_qty=2)
        page = self.page(f"/admin/catalog/product/{product.pk}/change/")
        self.assertIn("В наличии, 2 шт: 489 000 ₽", page)
        self.assertIn("Под заказ: 467 000 ₽", page)
        self.assertIn("Цена юаня 13.81 ₽", page)

    def test_change_form_without_rate_or_offers(self):
        config = CatalogSettings.load()
        config.rate_method = None
        config.save()
        product = bike(is_orderable=False)
        page = self.page(f"/admin/catalog/product/{product.pk}/change/")
        self.assertIn("В наличии: нет", page)
        self.assertIn("Предзаказ выключен", page)
        self.assertIn("Курса нет", page)

    def test_add_form_has_no_prices_yet(self):
        self.assertIn("Появятся после сохранения.", self.page("/admin/catalog/product/add/"))

    def form(self, **fields):
        data = {
            "brand": Brand.objects.get_or_create(name="Arctic Leopard")[0].pk,
            "model": "EX800", "powertrain": Product.ELECTRIC, "stock_qty": "0", "sort": "0",
            "is_orderable": "on", "is_published": "on",
            "photos-TOTAL_FORMS": "0", "photos-INITIAL_FORMS": "0",
            "extra_specs-TOTAL_FORMS": "1", "extra_specs-INITIAL_FORMS": "0",
            "extra_specs-0-name": "Реверс", "extra_specs-0-value": "есть", "extra_specs-0-sort": "0",
        }
        data.update(fields)
        return data

    def test_manager_adds_a_bike(self):
        response = self.client.post(
            "/admin/catalog/product/add/",
            self.form(power_kw="25", battery_voltage_v="74", battery_capacity_ah="75"),
        )
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(model="EX800")
        self.assertEqual(product.slug, "arctic-leopard-ex800")
        self.assertEqual(product.power_kw, D("25"))
        self.assertEqual([(s.name, s.value) for s in product.extra_specs.all()], [("Реверс", "есть")])

    def test_admin_refuses_engine_fields_on_electric(self):
        response = self.client.post("/admin/catalog/product/add/", self.form(displacement_cc="300"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "У этого типа байка такого параметра нет")
        self.assertFalse(Product.objects.exists())

    def test_settings_are_a_single_page(self):
        settings_id = CatalogSettings.load().pk
        self.assertIn("Цена юаня 13.81 ₽", self.page(f"/admin/catalog/catalogsettings/{settings_id}/change/"))
        self.assertEqual(self.client.get("/admin/catalog/catalogsettings/add/").status_code, 403)
        self.assertEqual(
            self.client.get(f"/admin/catalog/catalogsettings/{settings_id}/delete/").status_code, 403
        )
        CatalogSettings.objects.all().delete()
        self.assertEqual(self.client.get("/admin/catalog/catalogsettings/add/").status_code, 200)

    def test_rouble_format(self):
        self.assertEqual(rub(None), "по запросу")
        self.assertEqual(rub(D("467000")), "467 000 ₽")
        self.assertEqual(rub(D("1234567.4")), "1 234 567 ₽")


class SeedDemoTests(TestCase):
    def seed(self):
        call_command("seed_demo", stdout=StringIO())

    def test_catalog_is_ready_after_seed_and_seed_repeats_safely(self):
        self.seed()
        self.seed()
        self.assertEqual(CatalogSettings.load().rate_method.code, PaymentMethod.CODE_QR)
        self.assertEqual(
            sorted(Product.objects.values_list("powertrain", flat=True)),
            [Product.ELECTRIC, Product.ICE_4T],
        )
        for product in Product.objects.all():
            with self.subTest(product=product.title):
                product.full_clean()

    def test_seed_keeps_the_rate_chosen_in_admin(self):
        self.seed()
        config = CatalogSettings.load()
        config.rate_method = PaymentMethod.objects.get(code=PaymentMethod.CODE_CASH_MOSCOW)
        config.save()
        self.seed()
        self.assertEqual(CatalogSettings.load().rate_method.code, PaymentMethod.CODE_CASH_MOSCOW)

    def test_seed_leaves_a_real_catalog_alone(self):
        bike(brand="Arctic Leopard", model="EX800")
        self.seed()
        self.assertEqual(list(Product.objects.values_list("model", flat=True)), ["EX800"])
