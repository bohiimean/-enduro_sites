"""Ворота кабинета: вход по почте с подтверждением кодом, привязка номера и
«кабинет отдаёт только своё».

Ходим теми же путями, что и Nuxt: allauth headless (`/_allauth/browser/v1/...`)
и наш DRF, с настоящей проверкой CSRF (`enforce_csrf_checks=True`). Иначе
тесты проходили бы там, где браузер получает 403.

Почта — `locmem` (тестовый раннер Django подменяет бэкенд сам), код
достаётся из тела письма.
"""
import re
import time
from unittest import mock

from allauth.account.models import EmailAddress
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase

from .models import PhoneNumber, User

AUTH = "/_allauth/browser/v1/auth"
ME = "/api/v1/account/me/"
PHONES = "/api/v1/account/phones/"
PASSWORD = "Kx7-enduro-2026"


class ApiClient(Client):
    """Тестовый клиент, который ведёт себя как фронтенд: JSON в теле и
    CSRF-токен из cookie в заголовке.

    Токен читается заново перед каждым запросом — он меняется в момент входа
    (allauth зовёт `rotate_token`), и запомненный один раз даёт 403.
    """

    def __init__(self):
        super().__init__(enforce_csrf_checks=True)
        # allauth ставит cookie csrftoken на любом своём GET — как при загрузке
        # страницы во фронтенде.
        self.get(f"{AUTH}/session")

    def _csrf(self) -> dict:
        return {"HTTP_X_CSRFTOKEN": self.cookies["csrftoken"].value}

    def post_json(self, path, data=None):
        return self.post(path, data or {}, content_type="application/json", **self._csrf())

    def patch_json(self, path, data):
        return self.patch(path, data, content_type="application/json", **self._csrf())

    def delete_csrf(self, path):
        return self.delete(path, **self._csrf())

    def is_logged_in(self) -> bool:
        return self.get(f"{AUTH}/session").status_code == 200


def last_code(email: str) -> str:
    message = [m for m in mail.outbox if email in m.to][-1]
    return re.search(r"\b\d{6}\b", message.body).group(0)


class AuthTestCase(TestCase):
    def setUp(self):
        # Лимиты allauth (попытки входа, пауза между письмами) живут в кеше.
        cache.clear()

    def signup(self, email="rider@example.com") -> ApiClient:
        client = ApiClient()
        response = client.post_json(f"{AUTH}/signup", {"email": email, "password": PASSWORD})
        # 401 — не ошибка: аккаунт создан, но вход ждёт подтверждения адреса.
        self.assertEqual(response.status_code, 401, response.content)
        return client

    def signed_in(self, email="rider@example.com") -> ApiClient:
        client = self.signup(email)
        response = client.post_json(f"{AUTH}/email/verify", {"key": last_code(email)})
        self.assertEqual(response.status_code, 200, response.content)
        return client


class EmailVerificationGateTests(AuthTestCase):
    """Ворота жёсткие: до подтверждения адреса вход не пускает."""

    def test_signup_sends_six_digit_code_and_does_not_log_in(self):
        client = self.signup()

        self.assertEqual(len(mail.outbox), 1)
        self.assertRegex(last_code("rider@example.com"), r"^\d{6}$")
        self.assertFalse(client.is_logged_in())
        self.assertIn(client.get(ME).status_code, (401, 403))

    def test_login_with_right_password_is_refused_until_verified(self):
        self.signup()
        # Выжидаем паузу между письмами с кодом, см. тест ниже.
        cache.clear()

        client = ApiClient()
        response = client.post_json(
            f"{AUTH}/login", {"email": "rider@example.com", "password": PASSWORD}
        )

        self.assertEqual(response.status_code, 401)
        pending = [f["id"] for f in response.json()["data"]["flows"] if f.get("is_pending")]
        self.assertEqual(pending, ["verify_email"])
        self.assertFalse(client.is_logged_in())
        self.assertIn(client.get(ME).status_code, (401, 403))

    def test_login_within_ten_seconds_of_last_code_is_refused(self):
        """Особенность allauth, а не наш код: вход в неподтверждённый аккаунт
        отправляет новый код, между письмами пауза 10 секунд, и вход в эту
        паузу отбивается 400 с текстом «слишком много неудачных попыток входа»
        — хотя попытка первая и пароль верный. Если allauth это поменяет,
        тест упадёт, и текст на фронте можно будет пересмотреть."""
        self.signup()

        response = ApiClient().post_json(
            f"{AUTH}/login", {"email": "rider@example.com", "password": PASSWORD}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"][0]["code"], "too_many_login_attempts")

    def test_right_code_verifies_address_and_logs_in(self):
        client = self.signed_in()

        self.assertTrue(client.is_logged_in())
        self.assertTrue(
            EmailAddress.objects.get(email="rider@example.com").verified
        )
        response = client.get(ME)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["email_verified"])

    def test_wrong_code_is_rejected(self):
        client = self.signup()
        right = last_code("rider@example.com")
        wrong = "000000" if right != "000000" else "111111"

        response = client.post_json(f"{AUTH}/email/verify", {"key": wrong})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(client.is_logged_in())
        self.assertFalse(EmailAddress.objects.get(email="rider@example.com").verified)

    def test_three_wrong_codes_burn_the_attempt(self):
        """После трёх промахов верный код уже не принимается — только вход
        заново и новый код."""
        client = self.signup()
        right = last_code("rider@example.com")
        wrong = "000000" if right != "000000" else "111111"

        for _ in range(3):
            client.post_json(f"{AUTH}/email/verify", {"key": wrong})
        response = client.post_json(f"{AUTH}/email/verify", {"key": right})

        self.assertNotEqual(response.status_code, 200)
        self.assertFalse(client.is_logged_in())
        self.assertFalse(EmailAddress.objects.get(email="rider@example.com").verified)

    def test_expired_code_is_rejected(self):
        """Код живёт 15 минут."""
        client = self.signup()
        code = last_code("rider@example.com")

        later = time.time() + 16 * 60
        with mock.patch(
            "allauth.account.internal.flows.code_verification.time.time", return_value=later
        ):
            response = client.post_json(f"{AUTH}/email/verify", {"key": code})

        self.assertNotEqual(response.status_code, 200)
        self.assertFalse(client.is_logged_in())
        self.assertFalse(EmailAddress.objects.get(email="rider@example.com").verified)

    def test_code_from_another_signup_does_not_work(self):
        """Код привязан к сессии, в которой шла регистрация: чужой код в своей
        вкладке не подтверждает ни свой адрес, ни чужой."""
        alice = self.signup("alice@example.com")
        bob = self.signup("bob@example.com")
        alice_code = last_code("alice@example.com")
        if alice_code == last_code("bob@example.com"):
            self.skipTest("коды совпали случайно, шанс один на миллион")

        response = bob.post_json(f"{AUTH}/email/verify", {"key": alice_code})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(bob.is_logged_in())
        self.assertFalse(alice.is_logged_in())
        self.assertFalse(EmailAddress.objects.filter(verified=True).exists())

    def test_resend_works_without_login(self):
        """Иначе сбой почты при жёстких воротах запирает человека насмерть.
        По умолчанию у allauth переотправка выключена и отвечает 409."""
        client = self.signup()
        # Пауза между письмами — 10 секунд на адрес. Тест её не ждёт.
        cache.clear()

        response = client.post_json(f"{AUTH}/email/verify/resend")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(mail.outbox), 2)
        response = client.post_json(
            f"{AUTH}/email/verify", {"key": last_code("rider@example.com")}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(client.is_logged_in())

    def test_post_without_csrf_token_is_refused(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            f"{AUTH}/signup",
            {"email": "rider@example.com", "password": PASSWORD},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())


class CabinetOwnDataTests(AuthTestCase):
    """Кабинет отдаёт и меняет только данные вошедшего аккаунта."""

    def setUp(self):
        super().setUp()
        self.alice = self.signed_in("alice@example.com")
        self.bob = self.signed_in("bob@example.com")
        self.alice_phone = self.alice.post_json(PHONES, {"phone": "+7 912 345-67-89"}).json()

    def test_profile_is_own(self):
        self.assertEqual(self.alice.get(ME).json()["email"], "alice@example.com")
        self.assertEqual(self.bob.get(ME).json()["email"], "bob@example.com")

    def test_phone_list_is_own(self):
        self.assertEqual([p["phone"] for p in self.alice.get(PHONES).json()], ["+79123456789"])
        self.assertEqual(self.bob.get(PHONES).json(), [])

    def test_cannot_delete_foreign_phone(self):
        response = self.bob.delete_csrf(f"{PHONES}{self.alice_phone['id']}/")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(PhoneNumber.objects.filter(pk=self.alice_phone["id"]).exists())

    def test_can_delete_own_phone(self):
        response = self.alice.delete_csrf(f"{PHONES}{self.alice_phone['id']}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(PhoneNumber.objects.exists())

    def test_profile_edit_touches_only_own_name(self):
        response = self.bob.patch_json(ME, {"full_name": "Боб", "email": "alice@example.com"})

        self.assertEqual(response.status_code, 200)
        bob = User.objects.get(email="bob@example.com")
        self.assertEqual(bob.full_name, "Боб")
        # Почта через профиль не меняется: смена адреса — отдельный сценарий
        # allauth с подтверждением нового адреса.
        self.assertEqual(User.objects.get(email="alice@example.com").full_name, "")

    def test_phone_is_not_verified_by_the_user(self):
        """Подтверждение ставит канал (этап 6), а не сам пользователь."""
        response = self.bob.post_json(PHONES, {"phone": "+79990001122", "verified": True})

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(PhoneNumber.objects.get(phone="+79990001122").verified_at)
        self.assertFalse(self.bob.get(ME).json()["has_verified_phone"])


class PhoneFirstComeTests(AuthTestCase):
    """Номер занимает первый, кто его привязал."""

    def setUp(self):
        super().setUp()
        self.alice = self.signed_in("alice@example.com")
        self.bob = self.signed_in("bob@example.com")

    def test_second_account_gets_409_for_the_same_number_in_any_spelling(self):
        self.assertEqual(
            self.alice.post_json(PHONES, {"phone": "+7 (912) 345-67-89"}).status_code, 201
        )

        response = self.bob.post_json(PHONES, {"phone": "89123456789"})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Этот номер уже привязан к другому аккаунту.")
        self.assertEqual(PhoneNumber.objects.get().user.email, "alice@example.com")

    def test_rebinding_own_number_is_not_an_error(self):
        first = self.alice.post_json(PHONES, {"phone": "+79123456789"})
        again = self.alice.post_json(PHONES, {"phone": "8 912 345 67 89"})

        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["id"], first.json()["id"])
        self.assertEqual(PhoneNumber.objects.count(), 1)

    def test_non_russian_number_is_rejected(self):
        response = self.alice.post_json(PHONES, {"phone": "+1 202 555 0100"})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(PhoneNumber.objects.exists())

    def test_anonymous_cannot_bind_a_number(self):
        response = ApiClient().post_json(PHONES, {"phone": "+79123456789"})

        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(PhoneNumber.objects.exists())
