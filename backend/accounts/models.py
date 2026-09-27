"""Пользователь и реестр номеров телефона.

Логин — **почта + пароль** (решено 26.09.2026, отменяет решение от 22.09.2026 о
телефоне как логине). Причина смены одна: опора аккаунта должна проверяться
бесплатно. Телефон подтверждать нечем — SMS платные, MAX и Telegram не
реализованы, — а при телефоне-логине непроверенный номер закрывал бы кабинет
целиком. Почта проверяется письмом и заодно закрывает сброс пароля.

Номер при этом остаётся ключом KYC у alfabit: `Payer` уникален по телефону,
аккаунт держит только ссылку на номер. Сшивать идентичности не требуется —
связь аккаунт↔плательщик это FK, а не сопоставление по данным.

Подтверждение адреса живёт в `EmailAddress.verified` (модель allauth), своего
флага здесь нет и быть не должно — иначе два источника истины.

Номер — заявительный: пользователь вписал что угодно, никто это не проверял.
Поэтому подтверждение вынесено в `PhoneNumber.verified_at`, а не во флаг на
пользователе, и всё, что выводится по телефону, обязано читать это поле.
Каналов подтверждения (MAX / Telegram / SMS) пока нет — `verified_at` всегда
NULL, и проверка просто ни у кого не проходит. Ворота стоят с первого дня
специально: включение каналов на этапе 6 должно быть добавлением эндпоинта, а
не переделкой контроля доступа.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("Нужна почта — это логин")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Суперпользователь должен быть is_staff и is_superuser")
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    # `null=True` — задел под будущую регистрацию только по номеру: у такого
    # пользователя почты не будет, а менять уникальное поле на живых данных
    # дороже, чем завести его правильным сразу.
    # `blank=False` при этом обязателен: иначе форма сохранит пустую строку, и
    # второй такой пользователь упрётся в уникальность по ''.
    email = models.EmailField("почта (логин)", unique=True, null=True)
    full_name = models.CharField("ФИО", max_length=200, blank=True)
    is_active = models.BooleanField("активен", default=True)
    is_staff = models.BooleanField("доступ в админку", default=False)
    created_at = models.DateTimeField("создан", auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.full_name or self.email or f"#{self.pk}"

    @property
    def has_verified_phone(self) -> bool:
        return self.phones.filter(verified_at__isnull=False).exists()


class PhoneNumber(models.Model):
    """Номер, привязанный к аккаунту. Подтверждённый — ключ доступа к данным.

    Номеров у аккаунта может быть несколько: платить человек вправе с другого
    номера, чем тот, который привязал первым, а KYC у alfabit висит именно на
    номере платежа.

    Номер запрашивается в сценарии оплаты (этап 5), а не при регистрации — там
    же, где нужен, показываются и требования alfabit.
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
    # Уникален глобально: номер занимает первый, кто его привязал (решено
    # 27.09.2026). Второму аккаунту — отказ «номер уже привязан к другому
    # аккаунту». Забрать номер можно будет только подтверждением владения,
    # когда на этапе 6 появятся каналы: подтверждённый владелец отвязывает
    # номер у неподтверждённого аккаунта. Это эндпоинт, а не смена схемы.
    #
    # Принятый риск на сейчас: номер можно занять чужой. Атака бессмысленна —
    # занявший не видит ни ФИО по паспорту (его отдаём только тому аккаунту,
    # который сам загружал документы), ни заказов (они закрыты до verified_at).
    phone = models.CharField("телефон", max_length=16, unique=True)
    verified_at = models.DateTimeField("подтверждён", null=True, blank=True)
    verification_method = models.CharField(
        "способ подтверждения", max_length=16, choices=METHOD_CHOICES, blank=True
    )
    created_at = models.DateTimeField("добавлен", auto_now_add=True)

    class Meta:
        verbose_name = "номер телефона"
        verbose_name_plural = "номера телефонов"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.phone}{'' if self.verified_at else ' (не подтверждён)'}"

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None

    def mark_verified(self, method: str) -> None:
        """Ставится каналом подтверждения. Этап 6 — сейчас никто не вызывает."""
        self.verified_at = timezone.now()
        self.verification_method = method
        self.save(update_fields=["verified_at", "verification_method"])
