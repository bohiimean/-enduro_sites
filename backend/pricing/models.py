"""Курс: сырые котировки и наценки.

Разделение ролей зафиксировано в CLAUDE.md и здесь только исполняется:

* `rate-service` (этап 2, за границей) отдаёт **только сырые котировки** —
  никакой бизнес-логики;
* наценки, делитель юаня и тарифные уровни живут **здесь**, в БД, правятся
  в админке, и по ним считается витрина;
* бот на этапе 7 переключается на наш `/api/v1/pricing/`, чтобы цена считалась
  в одном месте.

Наценки бывают двух разных видов, одним полем не обойтись:
* `multiplier` — коэффициент: `курс × 1.045` (Rapira, alfabit);
* `rub_add`   — прибавка в рублях к курсу USD/RUB: `(курс + 2.6) / 6.63`
  (наличные в Москве).
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


class RateSource(models.Model):
    """Источник котировки. Коды совпадают с ключами ответа `rate-service`."""

    CODE_RAPIRA = "rapira"
    CODE_INVESTING = "investing"
    CODE_ALFABIT = "alfabit_showcase"

    code = models.SlugField("код", max_length=32, unique=True)
    title = models.CharField("название", max_length=100)
    description = models.CharField("комментарий", max_length=255, blank=True)
    is_active = models.BooleanField("активен", default=True)

    class Meta:
        verbose_name = "источник котировки"
        verbose_name_plural = "источники котировок"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.title or self.code

    @property
    def latest_quote(self) -> "RateQuote | None":
        return self.quotes.order_by("-fetched_at").first()


class RateQuote(models.Model):
    """Котировка на момент времени. Таблица append-only.

    Историю держим намеренно: объём копеечный, а когда клиент спросит «почему
    вчера цена была такой» — ответ будет. Оттуда же потом график.
    """

    source = models.ForeignKey(
        RateSource, verbose_name="источник", on_delete=models.CASCADE, related_name="quotes"
    )
    value = models.DecimalField("значение", max_digits=18, decimal_places=6)
    # Время, которым датирует котировку сам источник, — не время записи в БД.
    fetched_at = models.DateTimeField("получена")
    created_at = models.DateTimeField("записана", auto_now_add=True)

    class Meta:
        verbose_name = "котировка"
        verbose_name_plural = "котировки"
        ordering = ["-fetched_at"]
        indexes = [models.Index(fields=["source", "-fetched_at"])]
        constraints = [
            models.UniqueConstraint(fields=["source", "fetched_at"], name="uniq_source_fetched_at")
        ]

    def __str__(self) -> str:
        return f"{self.source.code} = {self.value} ({self.fetched_at:%d.%m %H:%M})"


class PaymentMethod(models.Model):
    """Способ оплаты на витрине: одна строка на сайте и в сообщении бота."""

    CODE_QR = "qr"
    CODE_QR_KYC = "qr_kyc"
    CODE_CASH_MOSCOW = "cash_moscow"

    code = models.SlugField("код", max_length=32, unique=True)
    title = models.CharField("заголовок", max_length=120)
    subtitle = models.CharField("подзаголовок", max_length=255, blank=True)
    note = models.TextField("примечание для клиента", blank=True)
    source = models.ForeignKey(
        RateSource,
        verbose_name="источник курса",
        on_delete=models.PROTECT,
        related_name="methods",
    )
    is_active = models.BooleanField("показывать", default=True)
    sort = models.PositiveIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "способ оплаты"
        verbose_name_plural = "способы оплаты"
        ordering = ["sort", "id"]

    def __str__(self) -> str:
        return self.title


class MarkupRule(models.Model):
    """Наценка способа оплаты — с типом, порогом суммы и окном действия.

    Окно действия заведено сознательно: в боте `get_usd_rate_info()` проверяет
    только будний/выходной день, никакой проверки времени там нет, при этом
    текст обещает «VIP курс действует с 12:30 до 16:00 в будний день». На
    сайте это должно быть данными, а не расхождением между кодом и текстом.
    """

    KIND_MULTIPLIER = "multiplier"
    KIND_RUB_ADD = "rub_add"
    KIND_CHOICES = [
        (KIND_MULTIPLIER, "Коэффициент (курс × значение)"),
        (KIND_RUB_ADD, "Прибавка в рублях (курс + значение)"),
    ]

    method = models.ForeignKey(
        PaymentMethod, verbose_name="способ оплаты", on_delete=models.CASCADE,
        related_name="markups",
    )
    label = models.CharField("подпись", max_length=120, help_text="«Стандарт», «от 300 000 ₽»")
    kind = models.CharField("тип наценки", max_length=16, choices=KIND_CHOICES)
    value = models.DecimalField("значение", max_digits=10, decimal_places=4)
    threshold_rub = models.DecimalField(
        "порог суммы, ₽", max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Пусто — уровень действует на любую сумму.",
    )
    weekdays = models.CharField(
        "дни недели", max_length=7, blank=True,
        validators=[RegexValidator(r"^[1-7]{0,7}$", "Только цифры 1–7, без разделителей.")],
        help_text="1 — понедельник … 7 — воскресенье. Пусто — все дни.",
    )
    time_from = models.TimeField("действует с", null=True, blank=True)
    time_to = models.TimeField("действует до", null=True, blank=True)
    is_active = models.BooleanField("активна", default=True)
    sort = models.PositiveIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "наценка"
        verbose_name_plural = "наценки"
        ordering = ["method", "sort", "id"]

    def __str__(self) -> str:
        sign = "×" if self.kind == self.KIND_MULTIPLIER else "+"
        return f"{self.method.code}: {self.label} ({sign}{self.value})"

    def clean(self) -> None:
        if (self.time_from is None) != (self.time_to is None):
            raise ValidationError("Окно действия задаётся обеими границами или ни одной.")

    def applies_at(self, moment) -> bool:
        """Действует ли уровень в указанный момент (время местное, МСК)."""
        if not self.is_active:
            return False
        if self.weekdays and str(moment.isoweekday()) not in self.weekdays:
            return False
        if self.time_from and self.time_to:
            now = moment.time()
            if self.time_from <= self.time_to:
                return self.time_from <= now <= self.time_to
            # Окно через полночь.
            return now >= self.time_from or now <= self.time_to
        return True

    def apply(self, rate: Decimal) -> Decimal:
        if self.kind == self.KIND_MULTIPLIER:
            return rate * self.value
        return rate + self.value


class PricingSettings(models.Model):
    """Единственная строка с общими параметрами расчёта."""

    cny_divisor = models.DecimalField(
        "юаней за доллар", max_digits=8, decimal_places=4, default=Decimal("6.63"),
        help_text="Цена юаня = курс / этот делитель. Прод считает по 6.63 — "
                  "не менять без явного запроса.",
    )
    stale_after_minutes = models.PositiveIntegerField(
        "котировка устарела через, мин", default=45,
        help_text="После этого срока цена показывается с пометкой времени.",
    )
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "параметры расчёта"
        verbose_name_plural = "параметры расчёта"

    def __str__(self) -> str:
        return "Параметры расчёта"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "PricingSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
