"""Ворота оплаты. Alfabit подменён: живые ключи в тестах не нужны, а сеть —
тем более.

Главное, что здесь держится:
- статус KYC и платёж — только по своим номерам и только свои;
- ФИО по паспорту — только аккаунту, который сам загружал документы;
- фото паспорта не ложатся на диск, даже большие;
- без пройденного KYC платёж не создаётся, лимиты проверяются до alfabit;
- сумма считается по свежему курсу, а без него — по свежей котировке из БД
  или никак.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.core.cache import cache
from django.core.files.uploadedfile import InMemoryUploadedFile, SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import PhoneNumber, User
from pricing.models import MarkupRule, PaymentMethod, PricingSettings, RateQuote, RateSource

from . import pricing, services
from .admin import PaymentAdmin
from .alfabit import AlfabitError
from .models import KycDocument, Payer, Payment
from .pricing import PaymentPrice, PriceUnavailable, payment_price

PHONE = "+79123456789"
APPROVED = {"kyc_status": "approved", "processing": False, "manual_review": False,
            "expected_payer_name": "Иванов Иван Иванович"}


def fake_client(**overrides):
    client = mock.Mock()
    client.get_payer.return_value = dict(APPROVED)
    client.upload_payer_document.return_value = {
        "kyc_status": "pending", "processing": True, "low_confidence": False,
    }
    client.create_checkout_payment.return_value = {"status": "created", "payment_uid": "uid-1"}
    client.get_checkout_payment.return_value = {"status": "created", "qr_url": "https://qr/1"}
    for name, value in overrides.items():
        setattr(client, name, value)
    return client


FIXED_PRICE = PaymentPrice(
    rate=Decimal("85.64"), price_per_cny=Decimal("13.14"),
    fetched_at=timezone.now(), fresh=True,
)


class PaymentsTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.alice = User.objects.create_user("alice@example.com", "x")
        self.bob = User.objects.create_user("bob@example.com", "x")
        self.phone = PhoneNumber.objects.create(user=self.alice, phone=PHONE)
        self.client_alfabit = fake_client()
        patcher = mock.patch("payments.views.get_client", return_value=self.client_alfabit)
        patcher.start()
        self.addCleanup(patcher.stop)

    def as_user(self, user) -> Client:
        client = Client()
        client.force_login(user)
        return client

    def upload(self, client, phone_id=None, size=1024, consent=True):
        return client.post("/api/v1/payments/documents/", {
            "phone_id": phone_id or self.phone.pk,
            "passport_main": SimpleUploadedFile("main.jpg", b"x" * size, "image/jpeg"),
            "passport_registration": SimpleUploadedFile("reg.jpg", b"y" * size, "image/jpeg"),
            "consent": "true" if consent else "false",
        })

    def create_payment(self, client, amount="1000", phone_id=None):
        with mock.patch("payments.views.payment_price", return_value=FIXED_PRICE):
            return client.post(
                "/api/v1/payments/",
                {"phone_id": phone_id or self.phone.pk, "amount_cny": amount},
                content_type="application/json",
            )


class KycAccessTests(PaymentsTestCase):
    def test_status_of_own_number(self):
        response = self.as_user(self.alice).get(f"/api/v1/payments/kyc/{self.phone.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kyc_status"], "approved")
        # ФИО на шаге статуса не отдаём вовсе — только на шаге QR.
        self.assertNotIn("Иванов", response.content.decode())

    def test_status_of_foreign_number_is_404_and_alfabit_is_not_asked(self):
        response = self.as_user(self.bob).get(f"/api/v1/payments/kyc/{self.phone.pk}/")

        self.assertEqual(response.status_code, 404)
        self.client_alfabit.get_payer.assert_not_called()

    def test_anonymous_gets_nothing(self):
        for path in ["/api/v1/payments/", f"/api/v1/payments/kyc/{self.phone.pk}/"]:
            with self.subTest(path=path):
                self.assertIn(Client().get(path).status_code, (401, 403))

    def test_status_is_rate_limited(self):
        client = self.as_user(self.alice)
        codes = [
            client.get(f"/api/v1/payments/kyc/{self.phone.pk}/").status_code for _ in range(31)
        ]
        self.assertEqual(codes[-1], 429)


class DocumentsUploadTests(PaymentsTestCase):
    def setUp(self):
        super().setUp()
        self.client_alfabit.get_payer.return_value = {"kyc_status": "not_started"}

    def test_both_pages_go_to_alfabit_and_leave_a_trace(self):
        response = self.upload(self.as_user(self.alice))

        self.assertEqual(response.status_code, 201, response.content)
        sent = [c.args[1] for c in self.client_alfabit.upload_payer_document.call_args_list]
        self.assertEqual(sent, ["passport_main", "passport_registration"])
        docs = KycDocument.objects.filter(payer__phone=PHONE)
        self.assertEqual(docs.count(), 2)
        self.assertTrue(all(d.uploaded_by == self.alice and d.consent_at for d in docs))
        # Заявка встала под наблюдение worker.
        self.assertIsNotNone(Payer.objects.get(phone=PHONE).watch_since)

    def test_big_photo_stays_in_memory(self):
        """Django по умолчанию пишет файлы больше 2.5 МБ во временный файл на
        диске. Паспорт на диск не ложится ни при каком размере."""
        self.upload(self.as_user(self.alice), size=6 * 1024 * 1024)

        files = [c.args[2] for c in self.client_alfabit.upload_payer_document.call_args_list]
        self.assertEqual(len(files), 2)
        for file in files:
            self.assertIsInstance(file, InMemoryUploadedFile)

    def test_without_consent_nothing_is_sent(self):
        response = self.upload(self.as_user(self.alice), consent=False)

        self.assertEqual(response.status_code, 400)
        self.client_alfabit.upload_payer_document.assert_not_called()

    def test_foreign_number_is_404(self):
        response = self.upload(self.as_user(self.bob))

        self.assertEqual(response.status_code, 404)
        self.client_alfabit.upload_payer_document.assert_not_called()

    def test_no_resend_while_operator_reviews(self):
        """Дока запрещает переотправку тех же файлов при manual_review."""
        Payer.objects.create(phone=PHONE, kyc_status="pending", manual_review=True)

        response = self.upload(self.as_user(self.alice))

        self.assertEqual(response.status_code, 409)
        self.client_alfabit.upload_payer_document.assert_not_called()

    def test_low_confidence_is_kept(self):
        """low_confidence приходит только в ответе на загрузку."""
        self.client_alfabit.upload_payer_document.return_value = {
            "kyc_status": "pending", "processing": True, "low_confidence": True,
        }
        response = self.upload(self.as_user(self.alice))

        self.assertTrue(all(d["low_confidence"] for d in response.json()["documents"]))


class PayerNameVisibilityTests(PaymentsTestCase):
    """ФИО по паспорту — только тому аккаунту, который сам загружал документы."""

    def test_uploader_sees_name_on_qr_step(self):
        payer = Payer.objects.create(phone=PHONE, **APPROVED)
        KycDocument.objects.create(payer=payer, doc_type="passport_main", uploaded_by=self.alice)

        response = self.create_payment(self.as_user(self.alice))

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["payer_name"], "Иванов Иван Иванович")

    def test_number_bound_without_upload_does_not_reveal_name(self):
        """Верификацию прошёл кто-то раньше (например, через бота) — привязка
        того же номера не даёт узнать ФИО."""
        response = self.create_payment(self.as_user(self.alice))

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["payer_name"])

    def test_next_owner_of_the_number_does_not_see_name(self):
        payer = Payer.objects.create(phone=PHONE, **APPROVED)
        KycDocument.objects.create(payer=payer, doc_type="passport_main", uploaded_by=self.alice)
        self.phone.delete()
        bob_phone = PhoneNumber.objects.create(user=self.bob, phone=PHONE)

        response = self.create_payment(self.as_user(self.bob), phone_id=bob_phone.pk)

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["payer_name"])


class PaymentCreateTests(PaymentsTestCase):
    def test_created_with_real_ip_and_fixed_price(self):
        response = self.as_user(self.alice)
        with mock.patch("payments.views.payment_price", return_value=FIXED_PRICE):
            response = response.post(
                "/api/v1/payments/", {"phone_id": self.phone.pk, "amount_cny": "1000"},
                content_type="application/json",
                HTTP_X_REAL_IP="203.0.113.7", HTTP_USER_AGENT="Mozilla/5.0 test",
            )

        self.assertEqual(response.status_code, 201, response.content)
        payment = Payment.objects.get()
        self.assertEqual(payment.amount_rub, Decimal("13140.00"))
        self.assertEqual(payment.price_per_cny, Decimal("13.14"))
        self.assertEqual(payment.payment_uid, "uid-1")
        kwargs = self.client_alfabit.create_checkout_payment.call_args.kwargs
        self.assertEqual(kwargs["payer_ip"], "203.0.113.7")
        self.assertEqual(kwargs["payer_user_agent"], "Mozilla/5.0 test")
        self.assertEqual(kwargs["amount"], "13140.00")

    def test_refused_without_approved_kyc(self):
        self.client_alfabit.get_payer.return_value = {"kyc_status": "pending", "processing": True}

        response = self.create_payment(self.as_user(self.alice))

        self.assertEqual(response.status_code, 409)
        self.client_alfabit.create_checkout_payment.assert_not_called()
        self.assertFalse(Payment.objects.exists())

    def test_foreign_number_is_404(self):
        response = self.create_payment(self.as_user(self.bob))

        self.assertEqual(response.status_code, 404)
        self.client_alfabit.create_checkout_payment.assert_not_called()

    def test_operation_limit(self):
        # 8000 ¥ × 13.14 = 105 120 ₽ > 100 000 ₽.
        response = self.create_payment(self.as_user(self.alice), amount="8000")

        self.assertEqual(response.status_code, 400)
        self.client_alfabit.create_checkout_payment.assert_not_called()

    def test_daily_limit_counts_paid_and_fresh_unpaid(self):
        client = self.as_user(self.alice)
        self.assertEqual(self.create_payment(client, amount="7000").status_code, 201)  # 91 980 ₽
        Payment.objects.update(status=Payment.STATUS_PAID)

        response = self.create_payment(client, amount="1000")  # ещё 13 140 ₽

        self.assertEqual(response.status_code, 400)
        self.assertIn("Суточный лимит", response.json()["detail"])

    def test_old_unpaid_payment_does_not_hold_the_limit(self):
        client = self.as_user(self.alice)
        self.create_payment(client, amount="7000")
        Payment.objects.update(created_at=timezone.now() - timedelta(hours=2))

        self.assertEqual(self.create_payment(client, amount="1000").status_code, 201)

    def test_kyc_required_from_alfabit_sends_back_to_verification(self):
        self.client_alfabit.create_checkout_payment.return_value = {
            "status": "kyc_required", "payer_status": "pending",
        }
        response = self.create_payment(self.as_user(self.alice))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Payment.objects.get().status, Payment.STATUS_FAILED)

    def test_alfabit_down_leaves_a_failed_trace(self):
        self.client_alfabit.create_checkout_payment.side_effect = AlfabitError("NETWORK", "timeout")

        response = self.create_payment(self.as_user(self.alice))

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("NETWORK", response.json()["detail"])
        self.assertEqual(Payment.objects.get().status, Payment.STATUS_FAILED)

    @override_settings(ALFABIT_API_KEY="", ALFABIT_SECRET_KEY="")
    def test_no_keys_means_503(self):
        with mock.patch("payments.views.get_client", return_value=None):
            response = self.create_payment(self.as_user(self.alice))
        self.assertEqual(response.status_code, 503)


class PaymentStatusTests(PaymentsTestCase):
    def setUp(self):
        super().setUp()
        self.create_payment(self.as_user(self.alice))
        self.payment = Payment.objects.get()

    def test_foreign_payment_is_404(self):
        self.assertEqual(
            self.as_user(self.bob).get(f"/api/v1/payments/{self.payment.pk}/").status_code, 404
        )
        self.assertEqual(self.as_user(self.bob).get("/api/v1/payments/").json()["results"], [])

    def test_polling_picks_up_qr_and_payment(self):
        client = self.as_user(self.alice)
        data = client.get(f"/api/v1/payments/{self.payment.pk}/").json()
        self.assertEqual(data["qr_url"], "https://qr/1")

        self.client_alfabit.get_checkout_payment.return_value = {"status": "succeeded"}
        Payment.objects.update(last_checked_at=None)
        data = client.get(f"/api/v1/payments/{self.payment.pk}/").json()

        self.assertEqual(data["status"], "paid")
        # На шаге после оплаты ФИО уже не показываем.
        self.assertIsNone(data["payer_name"])

    def test_paid_is_never_rolled_back(self):
        services.apply_payment_state(self.payment, {"status": "paid"})
        services.apply_payment_state(self.payment, {"status": "expired"})

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_PAID)

    def test_worker_watches_unpaid_payments(self):
        self.client_alfabit.get_checkout_payment.return_value = {"status": "paid"}

        services.watch_payments(self.client_alfabit)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_PAID)
        self.assertIsNotNone(self.payment.paid_at)


class KycWatchTests(PaymentsTestCase):
    def test_final_status_ends_the_watch(self):
        Payer.objects.create(phone=PHONE, kyc_status="pending", watch_since=timezone.now())

        services.watch_kyc(self.client_alfabit)

        payer = Payer.objects.get()
        self.assertEqual(payer.kyc_status, "approved")
        self.assertIsNone(payer.watch_since)

    def test_watch_gives_up_after_72_hours(self):
        Payer.objects.create(
            phone=PHONE, kyc_status="pending",
            watch_since=timezone.now() - timedelta(hours=73),
        )

        services.watch_kyc(self.client_alfabit)

        self.assertIsNone(Payer.objects.get().watch_since)
        self.client_alfabit.get_payer.assert_not_called()

    def test_network_error_keeps_the_watch(self):
        Payer.objects.create(phone=PHONE, kyc_status="pending", watch_since=timezone.now())
        self.client_alfabit.get_payer.side_effect = AlfabitError("NETWORK", "down")

        services.watch_kyc(self.client_alfabit)

        self.assertIsNotNone(Payer.objects.get().watch_since)


class IssueAdminTests(PaymentsTestCase):
    def test_only_paid_payments_can_be_marked_issued(self):
        self.create_payment(self.as_user(self.alice))
        self.create_payment(self.as_user(self.alice))
        paid, unpaid = Payment.objects.order_by("pk")
        Payment.objects.filter(pk=paid.pk).update(status=Payment.STATUS_PAID)
        manager = User.objects.create_superuser("manager@example.com", "x")
        request = mock.Mock(user=manager)

        admin = PaymentAdmin(Payment, AdminSite())
        with mock.patch.object(admin, "message_user"):
            admin.mark_issued(request, Payment.objects.all())

        paid.refresh_from_db()
        unpaid.refresh_from_db()
        self.assertEqual(paid.issued_by, manager)
        self.assertIsNotNone(paid.issued_at)
        self.assertIsNone(unpaid.issued_at)


class PaymentPriceTests(TestCase):
    """Сумма — по свежему курсу alfabit; без него — по котировке из БД, если
    ей не больше 20 минут; иначе платёж не создаётся."""

    def setUp(self):
        cache.clear()
        self.source = RateSource.objects.create(code=RateSource.CODE_ALFABIT, title="alfabit")
        method = PaymentMethod.objects.create(
            code=PaymentMethod.CODE_QR_KYC, title="QR + KYC", source=self.source
        )
        MarkupRule.objects.create(
            method=method, label="Стандарт", kind=MarkupRule.KIND_MULTIPLIER, value=Decimal("1.0175")
        )
        PricingSettings.load()

    def public(self, rate="84.13", fee="1.8", banks=True):
        def get(path, **params):
            if "fiat-converter" in path:
                return {"rate_effective": rate}
            if banks:
                return {"data": [{"bestchange_code": "SBPRUB", "deposit_fee_percent": fee}]}
            return {"data": []}
        return mock.patch.object(pricing, "_public_get", side_effect=get)

    def test_fresh_rate_with_fee_markup_and_divisor(self):
        with self.public():
            price = payment_price(Decimal("1000"))

        showcase = Decimal("84.13") * Decimal("1.018")
        expected = (showcase * Decimal("1.0175") / Decimal("6.63")).quantize(Decimal("0.01"))
        self.assertTrue(price.fresh)
        self.assertEqual(price.price_per_cny, expected)
        # Свежая котировка заодно легла на витрину.
        self.assertTrue(RateQuote.objects.filter(source=self.source).exists())

    def test_empty_bank_list_uses_last_known_fee(self):
        with self.public():
            first = payment_price()
        with self.public(banks=False):
            second = payment_price()
        self.assertEqual(first.price_per_cny, second.price_per_cny)

    def test_no_fee_ever_means_no_fresh_rate(self):
        """Без комиссии курс занижен на 1.8% — лучше не считать вовсе."""
        with self.public(banks=False), self.assertRaises(PriceUnavailable):
            payment_price()

    def test_falls_back_to_recent_stored_quote(self):
        RateQuote.objects.create(
            source=self.source, value=Decimal("85.64"),
            fetched_at=timezone.now() - timedelta(minutes=10),
        )
        with mock.patch.object(pricing, "_public_get", side_effect=ValueError("down")), \
                mock.patch.object(pricing, "get_client", return_value=None):
            price = payment_price()
        self.assertFalse(price.fresh)
        self.assertEqual(price.rate, Decimal("85.64"))

    def test_stale_stored_quote_is_not_used(self):
        RateQuote.objects.create(
            source=self.source, value=Decimal("85.64"),
            fetched_at=timezone.now() - timedelta(minutes=30),
        )
        with mock.patch.object(pricing, "_public_get", side_effect=ValueError("down")), \
                mock.patch.object(pricing, "get_client", return_value=None), \
                self.assertRaises(PriceUnavailable):
            payment_price()
