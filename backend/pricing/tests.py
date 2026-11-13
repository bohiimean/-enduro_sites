from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import Brand, CatalogSettings, Product
from payments.pricing import PriceUnavailable, payment_price
from .models import PaymentMethod, RateQuote, RateSource
from .services import build_showcase, fetch_quotes


class ActiveSourcesTests(TestCase):
    def setUp(self):
        call_command("seed_demo", no_products=True, stdout=StringIO())

    def test_alfabit_is_hidden_even_if_enabled_in_database(self):
        PaymentMethod.objects.create(code="legacy_investing", title="Старый тариф",
                                     source=RateSource.objects.get(code="investing"))
        RateSource.objects.update(is_active=True)
        PaymentMethod.objects.update(is_active=True)
        self.assertEqual(
            {m.source_code for m in build_showcase().methods}, {"rapira"}
        )

    def test_disabled_payment_never_fetches_or_uses_stored_rate(self):
        RateQuote.objects.create(
            source=RateSource.objects.get(code="alfabit_showcase"),
            value=90, fetched_at=timezone.now(),
        )
        with patch("payments.pricing._fresh_showcase_rate") as fetch:
            with self.assertRaisesMessage(PriceUnavailable, "временно отключена"):
                payment_price(Decimal("1000"))
        fetch.assert_not_called()

    @override_settings(RATE_SERVICE_URL="https://rates.invalid")
    def test_old_service_payload_cannot_import_alfabit(self):
        with patch("pricing.services.requests.get") as get:
            get.return_value.json.return_value = {
                code: {"value": "90", "fetched_at": timezone.now().isoformat()}
                for code in ("rapira", "investing", "alfabit_showcase")
            }
            self.assertEqual(fetch_quotes(), 1)
        self.assertFalse(RateQuote.objects.filter(source__code="alfabit_showcase").exists())
        self.assertFalse(RateQuote.objects.filter(source__code="investing").exists())

    def test_repeat_seed_keeps_alfabit_disabled(self):
        PaymentMethod.objects.update(is_active=True)
        call_command("seed_demo", no_products=True, stdout=StringIO())
        self.assertFalse(PaymentMethod.objects.get(code="qr_kyc").is_active)
        self.assertFalse(RateSource.objects.get(code="alfabit_showcase").is_active)

    def test_cash_uses_rapira_plus_surcharge(self):
        RateQuote.objects.create(source=RateSource.objects.get(code="rapira"), value=90,
                                 fetched_at=timezone.now())
        cash = next(m for m in build_showcase().methods if m.code == "cash_moscow")
        self.assertEqual(cash.source_code, "rapira")
        self.assertEqual(len(cash.tiers), 1)
        self.assertEqual(cash.tiers[0].price_per_cny,
                         ((Decimal("90") + Decimal("1.15")) / Decimal("6.63")).quantize(Decimal("0.01")))

    def test_migration_preserves_old_rules_disabled_and_switches_cash(self):
        import importlib
        from types import SimpleNamespace
        from django.apps import apps
        from .models import MarkupRule

        cash = PaymentMethod.objects.get(code="cash_moscow")
        cash.source = RateSource.objects.get(code="investing")
        cash.save()
        old = MarkupRule.objects.create(method=cash, label="от 300 000 ₽", kind="rub_add",
                                       value=Decimal("2.1"), weekdays="12345", threshold_rub=300000)
        migrate = importlib.import_module("pricing.migrations.0003_rapira_only").use_rapira
        migrate(apps, SimpleNamespace(connection=SimpleNamespace(alias="default")))
        old.refresh_from_db()
        cash.refresh_from_db()
        self.assertFalse(old.is_active)
        self.assertEqual(old.value, Decimal("2.1"))
        self.assertEqual(cash.source.code, "rapira")
        call_command("seed_demo", no_products=True, stdout=StringIO())
        self.assertEqual(cash.markups.filter(is_active=True).count(), 1)

    @override_settings(RATE_SERVICE_URL="https://rates.invalid", RATE_REFRESH_SECONDS=30)
    def test_worker_pulls_cached_quotes_every_30_seconds(self):
        from worker.scheduler import build_scheduler
        job = build_scheduler().get_job("refresh_quotes")
        self.assertEqual(job.trigger.interval.total_seconds(), 30)

    def test_catalog_api_reprices_without_resaving_bike(self):
        bike = Product.objects.create(
            brand=Brand.objects.create(name="Test"), model="Dynamic", powertrain="electric",
            price_cny=Decimal("30000"), stock_qty=0, is_orderable=True,
        )
        url = f"/api/v1/catalog/products/{bike.slug}/"
        config = CatalogSettings.load()
        config.delivery_rub = 0
        config.order_markup_percent = 5
        config.round_to_rub = 1000
        config.save()
        now = timezone.now()
        source = RateSource.objects.get(code="rapira")
        RateQuote.objects.create(source=source, value=80, fetched_at=now - timedelta(minutes=1))
        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)
        RateQuote.objects.create(source=source, value=90, fetched_at=now)
        second = self.client.get(url)
        self.assertGreater(Decimal(second.json()["order"]["price_rub"]),
                           Decimal(first.json()["order"]["price_rub"]))
        self.assertEqual(second.json()["photos"], [])
        self.assertEqual(second.json()["description"], "")
        bike.refresh_from_db()
        self.assertEqual(bike.price_cny, Decimal("30000"))
