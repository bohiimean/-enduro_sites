"""Заказы. Состав полей взят с рабочего листа бота (`bot/services/sheets.py`).

Заказ может существовать без аккаунта: менеджер заводит его руками, а человек
привязывается позже. Показывать заказ в ЛК можно только по **подтверждённому**
номеру — см. `accounts.PhoneNumber`.
"""
from django.db import models

from accounts.models import User


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

    @property
    def title(self) -> str:
        return self.product_title or (str(self.product) if self.product else "—")

    @property
    def remainder(self) -> "models.DecimalField | object":
        """Остаток к доплате. Считается, а не хранится: два источника правды
        по деньгам разойдутся при первой же правке."""
        return self.price - self.paid
