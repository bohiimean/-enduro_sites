"""Заказы. Состав полей взят с рабочего листа бота (`bot/services/sheets.py`).

Заказ может существовать без аккаунта: менеджер заводит его руками в админке.
В кабинете заказ виден по номеру из `OrderPhone` (решено 26.10.2026) или если
менеджер привязал его к аккаунту полем «клиент».
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import User
from core.phone import to_e164


def _e164_or_error(value: str, field: str) -> str:
    phone = to_e164(value)
    if not phone:
        raise ValidationError({field: "Нужен российский номер, например +7 912 345-67-89."})
    return phone


class SupplyStatus(models.Model):
    """Справочник, а не choices: в листе это свободный текст, и менеджеру
    понадобится заводить свои значения без правки кода."""

    name = models.CharField("название", max_length=120, unique=True)
    sort = models.PositiveIntegerField("порядок", default=0)
    is_final = models.BooleanField("финальный", default=False)

    class Meta:
        verbose_name = "статус поставки"
        verbose_name_plural = "статусы поставки"
        ordering = ["sort", "name"]

    def __str__(self) -> str:
        return self.name


class Order(models.Model):
    user = models.ForeignKey(
        User, verbose_name="клиент", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="orders",
    )
    phone = models.CharField("телефон", max_length=16, db_index=True)
    full_name = models.CharField("ФИО", max_length=200, blank=True)
    city = models.CharField("город", max_length=120, blank=True)
    delivery_company = models.CharField("транспортная компания", max_length=120, blank=True)

    product = models.ForeignKey(
        "catalog.Product", verbose_name="байк", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="orders",
    )
    # Заказ может быть на позицию, которой нет в каталоге, — держим и текстом.
    product_title = models.CharField("позиция", max_length=255, blank=True)
    # Цвет и количество — колонки «Цвет» и «кол-во» листа заказов бота. Цвет
    # у заказа свой: в каталоге цвета модели перечислены текстом, а клиент
    # берёт один.
    color = models.CharField("цвет", max_length=60, blank=True)
    quantity = models.PositiveIntegerField("кол-во", default=1)

    price = models.DecimalField("цена, ₽", max_digits=12, decimal_places=2, default=0)
    paid = models.DecimalField("оплачено, ₽", max_digits=12, decimal_places=2, default=0)

    supply_status = models.ForeignKey(
        SupplyStatus, verbose_name="статус поставки", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="orders",
    )
    ordered_at = models.DateField("дата заказа", null=True, blank=True)
    comment = models.TextField("комментарий", blank=True)

    external_key = models.CharField("ключ импорта", max_length=120, blank=True, db_index=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        verbose_name = "заказ"
        verbose_name_plural = "заказы"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"№{self.pk} — {self.title} ({self.phone})"

    def clean(self):
        # Кабинет ищет заказы точным совпадением номера, поэтому в базе он
        # только в одном написании. Менеджер вправе вписать «8 912 …».
        self.phone = _e164_or_error(self.phone, "phone")

    @property
    def title(self) -> str:
        return self.product_title or (str(self.product) if self.product else "—")

    @property
    def remainder(self) -> "models.DecimalField | object":
        """Остаток к доплате. Считается, а не хранится: два источника правды
        по деньгам разойдутся при первой же правке."""
        return self.price - self.paid


class OrderPhone(models.Model):
    """Номер, по которому кабинет показывает заказы (решено 26.10.2026).

    Как в боте: человек вписывает номер и видит заказы, оформленные на него.
    Отличие от бота — номер **фиксируется**: первый ввод ставит его сразу, а
    сменить можно только заявкой, которую одобряет менеджер в админке. Иначе
    кабинет превращался бы в перебор чужих номеров, как поле ввода в боте.

    Номер заявительный, никто его не подтверждал. Принятый риск: вписав чужой
    номер первым, человек увидит чужие заказы, а владелец номера — отказ
    «уже привязан» и путь через менеджера. Закрывается каналами подтверждения
    (этап 6): тогда первый ввод станет подтверждением, а не заявлением.

    Это отдельный реестр, а не `accounts.PhoneNumber`: номера для оплаты
    человек привязывает и отвязывает сам, и через них фиксация обходилась бы.
    """

    user = models.OneToOneField(
        User, verbose_name="пользователь", on_delete=models.CASCADE, related_name="order_phone"
    )
    # Номер занимает первый: два аккаунта на одни заказы — это уже не «свои».
    phone = models.CharField("номер для заказов", max_length=16, unique=True)
    requested_phone = models.CharField("просит сменить на", max_length=16, blank=True)
    requested_at = models.DateTimeField("заявка от", null=True, blank=True)
    created_at = models.DateTimeField("указан", auto_now_add=True)
    changed_at = models.DateTimeField("сменён менеджером", null=True, blank=True)

    class Meta:
        verbose_name = "номер для заказов"
        verbose_name_plural = "номера для заказов"
        ordering = ["-requested_at", "-created_at"]

    def __str__(self) -> str:
        return f"{self.phone} — {self.user}"

    def clean(self):
        self.phone = _e164_or_error(self.phone, "phone")
        if self.requested_phone:
            self.requested_phone = _e164_or_error(self.requested_phone, "requested_phone")

    def request_change(self, phone: str) -> None:
        """Заявка на смену. Свой же номер отменяет заявку: человек передумал."""
        if phone == self.phone:
            self.requested_phone, self.requested_at = "", None
        else:
            self.requested_phone, self.requested_at = phone, timezone.now()
        self.save(update_fields=["requested_phone", "requested_at"])

    def approve_change(self) -> bool:
        """Одобрение менеджером. False — нечего одобрять или номер уже занят
        другим аккаунтом (его заняли, пока заявка ждала)."""
        new = self.requested_phone
        if not new or OrderPhone.objects.filter(phone=new).exclude(pk=self.pk).exists():
            return False
        self.phone, self.requested_phone, self.requested_at = new, "", None
        self.changed_at = timezone.now()
        self.save(update_fields=["phone", "requested_phone", "requested_at", "changed_at"])
        return True

    def reject_change(self) -> bool:
        if not self.requested_phone:
            return False
        self.requested_phone, self.requested_at = "", None
        self.save(update_fields=["requested_phone", "requested_at"])
        return True


def orders_for(user: User) -> "models.QuerySet[Order]":
    """Заказы, которые видит аккаунт: по его номеру для заказов и те, что
    менеджер привязал к нему руками."""
    match = models.Q(user=user)
    phone = OrderPhone.objects.filter(user=user).values_list("phone", flat=True).first()
    if phone:
        match |= models.Q(phone=phone)
    # Свежие заказы сверху; без даты — в конце, они обычно ещё не оформлены.
    return (
        Order.objects.filter(match)
        .select_related("supply_status")
        .order_by(models.F("ordered_at").desc(nulls_last=True), "-created_at")
    )
