"""Пользователь и подтверждение номера.

Логин — номер телефона (решено 22.09.2026). Причина не вкусовая: у alfabit
ключ KYC — телефон, верификация проверяется один раз и переиспользуется. При
входе по почте получились бы две независимые идентичности, которые пришлось бы
сшивать руками.

Номер при регистрации **заявительный** — вписать можно что угодно. Поэтому
подтверждение живёт отдельной сущностью (`PhoneNumber.verified_at`), а не
флагом на пользователе, и всё, что выводится по телефону, обязано читать это
поле. Каналов подтверждения (MAX / Telegram / SMS) пока нет — `verified_at`
всегда NULL, и проверка просто ни у кого не проходит. Ворота стоят с первого
дня специально: включение каналов на этапе 5 должно быть добавлением
эндпоинта, а не переделкой контроля доступа.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from core.phone import to_e164


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, phone: str, password: str | None, **extra):
        normalized = to_e164(phone)
        if not normalized:
            raise ValueError("Нужен российский номер в формате +7XXXXXXXXXX")
        user = self.model(phone=normalized, **extra)
        user.set_password(password)
        user.save(using=self._db)
        # Номер логина сразу заводится в реестре — неподтверждённым. Когда на
        # этапе 5 появятся каналы, подтверждать будет что.
        PhoneNumber.objects.get_or_create(user=user, phone=normalized)
        return user

    def create_user(self, phone: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(phone, password, **extra)

    def create_superuser(self, phone: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Суперпользователь должен быть is_staff и is_superuser")
        return self._create(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField("телефон", max_length=16, unique=True)
    full_name = models.CharField("ФИО", max_length=200, blank=True)
    # Не логин. Назначение — возможное восстановление пароля, решение не
    # принято (CLAUDE.md, «Открытые вопросы»). Поле заведено заранее, чтобы
    # не делать миграцию ради одной колонки.
    email = models.EmailField("почта (не логин)", blank=True)
    is_active = models.BooleanField("активен", default=True)
    is_staff = models.BooleanField("доступ в админку", default=False)
    created_at = models.DateTimeField("создан", auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.full_name or self.phone

    @property
    def has_verified_phone(self) -> bool:
        return self.phones.filter(verified_at__isnull=False).exists()


class PhoneNumber(models.Model):
    """Номер, привязанный к аккаунту. Подтверждённый — ключ доступа к данным.

    Номеров может быть несколько: платить человек вправе с другого номера, чем
    тот, по которому зашёл, а KYC у alfabit привязан именно к номеру платежа.
    """

    METHOD_MAX = "max"
    METHOD_TELEGRAM = "telegram"
    METHOD_SMS = "sms"
    METHOD_FLASHCALL = "flashcall"
    METHOD_CHOICES = [
        (METHOD_MAX, "MAX"),
        (METHOD_TELEGRAM, "Telegram"),
        (METHOD_SMS, "SMS"),
        (METHOD_FLASHCALL, "Звонок"),
    ]

    user = models.ForeignKey(
        User, verbose_name="пользователь", on_delete=models.CASCADE, related_name="phones"
    )
    phone = models.CharField("телефон", max_length=16)
    verified_at = models.DateTimeField("подтверждён", null=True, blank=True)
    verification_method = models.CharField(
        "способ подтверждения", max_length=16, choices=METHOD_CHOICES, blank=True
    )
    created_at = models.DateTimeField("добавлен", auto_now_add=True)

    class Meta:
        verbose_name = "номер телефона"
        verbose_name_plural = "номера телефонов"
        constraints = [
            models.UniqueConstraint(fields=["user", "phone"], name="uniq_user_phone"),
            # Уникальность — только среди подтверждённых. Заявительный номер
            # можно вписать кому угодно, и блокировать этим чужую регистрацию
            # он не должен. Политика на момент включения каналов:
            # подтверждённый владелец забирает номер.
            models.UniqueConstraint(
                fields=["phone"],
                condition=models.Q(verified_at__isnull=False),
                name="uniq_verified_phone",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.phone}{'' if self.verified_at else ' (не подтверждён)'}"

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None

    def mark_verified(self, method: str) -> None:
        """Ставится каналом подтверждения. Этап 5 — сейчас никто не вызывает."""
        self.verified_at = timezone.now()
        self.verification_method = method
        self.save(update_fields=["verified_at", "verification_method"])
