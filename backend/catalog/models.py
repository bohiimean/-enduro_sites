"""Каталог байков.

Мастер каталога — админка сайта (решено 11.10.2026). Характеристики и две цены
в лист Google Sheets не помещаются, поэтому импорт из него отменён. Бот до
этапа 8 читает свой `Лист2` как раньше: пока он не переедет на API, байк
ведётся в двух местах.

Рубли здесь не хранятся, кроме ручной цены «в наличии»: обе цены считаются на
лету от цены завода в юанях и курса (`catalog/pricing.py`).
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

_NON_NEGATIVE = [MinValueValidator(Decimal("0"))]


class Brand(models.Model):
    name = models.CharField("марка", max_length=100, unique=True)
    slug = models.SlugField("адрес", max_length=120, unique=True, blank=True)
    sort = models.PositiveIntegerField("порядок", default=0)
    is_active = models.BooleanField("активна", default=True)

    class Meta:
        verbose_name = "марка"
        verbose_name_plural = "марки"
        ordering = ["sort", "name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            # Кириллица в slugify пропадает целиком: без суффикса вторая марка,
            # записанная по-русски, упала бы на уникальности адреса.
            base = slugify(self.name, allow_unicode=False) or "brand"
            slug, n = base, 1
            while Brand.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)


class Product(models.Model):
    """Модель байка: одна карточка на модель, цвета перечисляются текстом.

    Наличие считается на модель целиком, без разбивки по цветам: покупку на
    сайте не оформляют, конкретный экземпляр уточняет менеджер.
    """

    ICE_4T = "ice_4t"
    ICE_2T = "ice_2t"
    ELECTRIC = "electric"
    POWERTRAIN_CHOICES = [
        (ICE_4T, "ДВС, 4-тактный"),
        (ICE_2T, "ДВС, 2-тактный"),
        (ELECTRIC, "Электро"),
    ]

    DOCS_EPTS = "epts"
    DOCS_NONE = "none"
    DOCUMENTS_CHOICES = [
        (DOCS_EPTS, "ЭПТС — можно поставить на учёт"),
        (DOCS_NONE, "Без ПТС — для бездорожья и спорта"),
    ]

    COOLING_CHOICES = [
        ("liquid", "жидкостное"),
        ("air", "воздушное"),
        ("oil_air", "масляно-воздушное"),
    ]
    STARTER_CHOICES = [
        ("electric", "электростартер"),
        ("kick", "кикстартер"),
        ("both", "электростартер и кик"),
    ]

    # Параметры, которые бывают только у одного типа. «Чужое» заполненное поле
    # на сайте не показалось бы — данные терялись бы молча, поэтому такое
    # сохранение отбивается в clean().
    ICE_ONLY = ("displacement_cc", "cooling", "fuel_system", "transmission", "starter", "fuel_tank_l")
    ELECTRIC_ONLY = ("battery_voltage_v", "battery_capacity_ah", "range_km", "charge_time_h")

    # --- Основное ---------------------------------------------------------
    brand = models.ForeignKey(
        Brand, verbose_name="марка", on_delete=models.PROTECT, related_name="products"
    )
    model = models.CharField(
        "модель", max_length=150, help_text="Без года: «Ultra Bee», «G9 Pro», «Z300 S7»."
    )
    model_year = models.PositiveSmallIntegerField(
        "год", null=True, blank=True, validators=[MinValueValidator(1990)]
    )
    powertrain = models.CharField("тип", max_length=16, choices=POWERTRAIN_CHOICES)
    tagline = models.CharField(
        "коротко", max_length=160, blank=True, help_text="Одна строка под названием в списке."
    )
    description = models.TextField("описание", blank=True)
    colors = models.CharField(
        "цвета", max_length=200, blank=True, help_text="Через запятую: «чёрный, белый»."
    )
    documents = models.CharField(
        "документы", max_length=8, choices=DOCUMENTS_CHOICES, blank=True
    )

    # --- Цена и наличие ---------------------------------------------------
    price_cny = models.DecimalField(
        "цена завода, ¥", max_digits=12, decimal_places=2, null=True, blank=True,
        validators=_NON_NEGATIVE,
        help_text="От неё по курсу считаются обе цены. Пусто — на сайте «цена по запросу».",
    )
    delivery_rub = models.DecimalField(
        "доставка до Москвы, ₽", max_digits=12, decimal_places=2, null=True, blank=True,
        validators=_NON_NEGATIVE,
        help_text="Пусто — общая из настроек каталога. 0 — доставка уже в цене завода.",
    )
    stock_qty = models.PositiveIntegerField("в наличии в Москве, шт", default=0)
    stock_price_rub = models.DecimalField(
        "цена в наличии вручную, ₽", max_digits=12, decimal_places=2, null=True, blank=True,
        validators=_NON_NEGATIVE,
        help_text="Пусто — считается от юаней с наценкой «в наличии». "
                  "Вписанную цену курс не трогает.",
    )
    is_orderable = models.BooleanField("принимаем предзаказ", default=True)
    lead_time = models.CharField(
        "срок поставки", max_length=60, blank=True,
        help_text="Пусто — общий из настроек каталога.",
    )

    # --- Характеристики: общие ---------------------------------------------
    engine = models.CharField(
        "двигатель / мотор", max_length=120, blank=True,
        help_text="«Zongshen NC300S», «PMSM, средний привод».",
    )
    power_hp = models.DecimalField(
        "мощность, л.с.", max_digits=5, decimal_places=1, null=True, blank=True,
        validators=_NON_NEGATIVE,
    )
    power_kw = models.DecimalField(
        "мощность, кВт", max_digits=5, decimal_places=1, null=True, blank=True,
        validators=_NON_NEGATIVE, help_text="У электро — пиковая.",
    )
    torque_nm = models.PositiveSmallIntegerField("крутящий момент, Н·м", null=True, blank=True)
    max_speed_kmh = models.PositiveSmallIntegerField("макс. скорость, км/ч", null=True, blank=True)
    weight_kg = models.DecimalField(
        "вес, кг", max_digits=5, decimal_places=1, null=True, blank=True,
        validators=_NON_NEGATIVE, help_text="Как в спецификации завода, обычно сухой.",
    )
    seat_height_mm = models.PositiveSmallIntegerField("высота по седлу, мм", null=True, blank=True)
    ground_clearance_mm = models.PositiveSmallIntegerField("клиренс, мм", null=True, blank=True)
    frame = models.CharField("рама", max_length=120, blank=True)
    fork = models.CharField("вилка", max_length=120, blank=True)
    shock = models.CharField("амортизатор", max_length=120, blank=True)
    brakes = models.CharField("тормоза", max_length=120, blank=True)
    wheels = models.CharField("колёса", max_length=60, blank=True, help_text="«21/18».")

    # --- Только ДВС --------------------------------------------------------
    displacement_cc = models.PositiveSmallIntegerField("объём, см³", null=True, blank=True)
    cooling = models.CharField("охлаждение", max_length=8, choices=COOLING_CHOICES, blank=True)
    fuel_system = models.CharField(
        "питание", max_length=80, blank=True, help_text="«карбюратор Keihin PWK 38», «инжектор»."
    )
    transmission = models.CharField(
        "КПП", max_length=80, blank=True, help_text="«6-ступенчатая»."
    )
    starter = models.CharField("запуск", max_length=8, choices=STARTER_CHOICES, blank=True)
    fuel_tank_l = models.DecimalField(
        "бак, л", max_digits=4, decimal_places=1, null=True, blank=True, validators=_NON_NEGATIVE
    )

    # --- Только электро ----------------------------------------------------
    battery_voltage_v = models.PositiveSmallIntegerField("батарея, В", null=True, blank=True)
    battery_capacity_ah = models.DecimalField(
        "батарея, А·ч", max_digits=5, decimal_places=1, null=True, blank=True,
        validators=_NON_NEGATIVE,
    )
    range_km = models.PositiveSmallIntegerField("запас хода, км", null=True, blank=True)
    charge_time_h = models.DecimalField(
        "зарядка, ч", max_digits=4, decimal_places=1, null=True, blank=True,
        validators=_NON_NEGATIVE,
    )

    # --- Публикация --------------------------------------------------------
    is_published = models.BooleanField("опубликован", default=True)
    slug = models.SlugField("адрес", max_length=200, unique=True, blank=True)
    sort = models.PositiveIntegerField("порядок", default=0)
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        verbose_name = "байк"
        verbose_name_plural = "байки"
        ordering = ["sort", "-created_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def title(self) -> str:
        parts = [self.brand.name, self.model]
        if self.model_year:
            parts.append(str(self.model_year))
        return " ".join(parts)

    @property
    def is_electric(self) -> bool:
        return self.powertrain == self.ELECTRIC

    def clean(self) -> None:
        super().clean()
        if not self.powertrain:
            return
        alien = self.ICE_ONLY if self.is_electric else self.ELECTRIC_ONLY
        errors = {
            name: "У этого типа байка такого параметра нет — очистите поле."
            for name in alien
            if getattr(self, name) not in (None, "")
        }
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.brand.name}-{self.model}-{self.model_year or ''}".strip("-"))
            slug, n = base or "bike", 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)


class ProductSpec(models.Model):
    """Характеристика сверх основных полей: реверс, рекуперация, режимы."""

    product = models.ForeignKey(
        Product, verbose_name="байк", on_delete=models.CASCADE, related_name="extra_specs"
    )
    name = models.CharField("параметр", max_length=80)
    value = models.CharField("значение", max_length=200)
    sort = models.PositiveIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "доп. характеристика"
        verbose_name_plural = "доп. характеристики"
        ordering = ["sort", "id"]

    def __str__(self) -> str:
        return f"{self.name}: {self.value}"


class ProductPhoto(models.Model):
    product = models.ForeignKey(
        Product, verbose_name="байк", on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField("файл", upload_to="catalog/%Y/%m")
    sort = models.PositiveIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "фото"
        verbose_name_plural = "фото"
        ordering = ["sort", "id"]

    def __str__(self) -> str:
        return f"Фото {self.product}"


class CatalogSettings(models.Model):
    """Единственная строка: по какому курсу и как из юаней получаются рубли."""

    rate_method = models.ForeignKey(
        "pricing.PaymentMethod", verbose_name="курс юаня — как у способа оплаты",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        help_text="Берётся цена юаня этого способа со страницы курса, уровень без порога "
                  "суммы. Пусто или способ выключен на витрине — цены от юаней не считаются.",
    )
    order_markup_percent = models.DecimalField(
        "наценка под заказ, %", max_digits=5, decimal_places=2, default=Decimal("5"),
        validators=_NON_NEGATIVE,
    )
    stock_markup_percent = models.DecimalField(
        "наценка в наличии, %", max_digits=5, decimal_places=2, default=Decimal("10"),
        validators=_NON_NEGATIVE,
    )
    delivery_rub = models.DecimalField(
        "доставка до Москвы, ₽", max_digits=12, decimal_places=2, default=Decimal("0"),
        validators=_NON_NEGATIVE, help_text="Для моделей, у которых своя не указана.",
    )
    lead_time = models.CharField(
        "срок поставки под заказ", max_length=60, blank=True,
        help_text="Для моделей, у которых свой не указан: «45–60 дней».",
    )
    round_to_rub = models.PositiveIntegerField(
        "округлять вверх до, ₽", default=1000, validators=[MinValueValidator(1)]
    )
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "настройки каталога"
        verbose_name_plural = "настройки каталога"

    def __str__(self) -> str:
        return "Настройки каталога"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "CatalogSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
