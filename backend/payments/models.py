"""Платежи через Alfabit (QR + KYC) и состояние верификации плательщика.

Главное отличие от бота: состояние живёт в БД. У бота `_pending` — словарь на
500 записей в памяти, `payment_uid` зашит в `callback_data` кнопки, а реестр
заявок KYC (`services/kyc_watch.py`) теряется при рестарте процесса. Здесь всё
это переживает перезапуск, и заявку можно досмотреть фоном без участия
человека.

Байтов документов тут нет и не будет: фото паспорта уходит в alfabit потоком,
у нас остаётся только след загрузки (`KycDocument`) и статус.
"""
from django.db import models

from accounts.models import User


class Payer(models.Model):
    """Плательщик у alfabit. Ключ — номер телефона, как у них."""

    STATUS_NOT_STARTED = "not_started"
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_NOT_STARTED, "Не начата"),
        (STATUS_PENDING, "На проверке"),
        (STATUS_APPROVED, "Пройдена"),
        (STATUS_REJECTED, "Отклонена"),
    ]

    phone = models.CharField("телефон", max_length=16, unique=True)
    kyc_status = models.CharField(
        "статус KYC", max_length=16, choices=STATUS_CHOICES, default=STATUS_NOT_STARTED
    )
    expected_payer_name = models.CharField("ФИО по паспорту", max_length=200, blank=True)
    # Три разных «pending» у alfabit различаются именно этими полями:
    # processing — идёт распознавание; manual_review — заявку забрал оператор
    # (переотправка тех же файлов запрещена докой); ни то ни другое — ждём
    # недостающий документ от человека.
    processing = models.BooleanField("идёт распознавание", default=False)
    manual_review = models.BooleanField("ручная проверка", default=False)
    last_checked_at = models.DateTimeField("последний опрос", null=True, blank=True)
    # Заявка под наблюдением: фоновая задача досматривает её до терминального
    # статуса. У бота этот реестр жил в памяти и умирал при рестарте.
    watch_since = models.DateTimeField("под наблюдением с", null=True, blank=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        verbose_name = "плательщик (KYC)"
        verbose_name_plural = "плательщики (KYC)"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.phone} — {self.get_kyc_status_display()}"

    @property
    def is_approved(self) -> bool:
        return self.kyc_status == self.STATUS_APPROVED


class Payment(models.Model):
    STATUS_CREATED = "created"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"

    # Наш идентификатор, уходит в alfabit как external_payment_id.
    external_payment_id = models.CharField("наш номер", max_length=64, unique=True)
    # Их идентификатор, появляется в ответе на создание платежа.
    payment_uid = models.CharField("номер у alfabit", max_length=64, blank=True, db_index=True)

    user = models.ForeignKey(
        User, verbose_name="клиент", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="payments",
    )
    payer = models.ForeignKey(
        Payer, verbose_name="плательщик", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="payments",
    )
    phone = models.CharField("телефон плательщика", max_length=16, db_index=True)

    amount_cny = models.DecimalField("сумма, ¥", max_digits=12, decimal_places=2)
    amount_rub = models.DecimalField("сумма, ₽", max_digits=12, decimal_places=2)
    # Курс и цену юаня фиксируем в момент создания: без них сумму потом не
    # объяснить ни клиенту, ни себе.
    rate_used = models.DecimalField("курс USDT/RUB", max_digits=18, decimal_places=6)
    price_per_cny = models.DecimalField("цена юаня, ₽", max_digits=12, decimal_places=2)

    status = models.CharField("статус", max_length=32, default=STATUS_CREATED)
    qr_url = models.URLField("ссылка на оплату", max_length=1000, blank=True)
    qr_payload = models.TextField("payload QR", blank=True)

    # То, чего у бота не было в принципе: настоящий IP и UA плательщика.
    payer_ip = models.GenericIPAddressField("IP плательщика", null=True, blank=True)
    payer_user_agent = models.CharField("User-Agent", max_length=500, blank=True)

    raw_response = models.JSONField("последний ответ alfabit", default=dict, blank=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)
    paid_at = models.DateTimeField("оплачен", null=True, blank=True)

    class Meta:
        verbose_name = "платёж"
        verbose_name_plural = "платежи"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.external_payment_id} — {self.amount_rub} ₽"


class KycDocument(models.Model):
    """След загрузки документа. Файла здесь нет — только факт и результат.

    `low_confidence` («распозналось плохо») приходит **только** в ответе на
    загрузку: в `GET /payers` этого поля нет, второго шанса его увидеть не
    будет. Поэтому сохраняем сразу.
    """

    TYPE_MAIN = "passport_main"
    TYPE_REGISTRATION = "passport_registration"
    TYPE_SELFIE = "selfie"
    TYPE_CHOICES = [
        (TYPE_MAIN, "Главная страница паспорта"),
        (TYPE_REGISTRATION, "Страница с пропиской"),
        (TYPE_SELFIE, "Селфи"),
    ]

    payer = models.ForeignKey(
        Payer, verbose_name="плательщик", on_delete=models.CASCADE, related_name="documents"
    )
    doc_type = models.CharField("тип документа", max_length=32, choices=TYPE_CHOICES)
    uploaded_at = models.DateTimeField("загружен", auto_now_add=True)
    low_confidence = models.BooleanField("распозналось плохо", null=True, blank=True)
    response = models.JSONField("ответ alfabit", default=dict, blank=True)

    class Meta:
        verbose_name = "документ KYC (след)"
        verbose_name_plural = "документы KYC (следы)"
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.payer.phone} — {self.get_doc_type_display()}"
