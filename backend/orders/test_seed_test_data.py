import tempfile
from io import StringIO

from allauth.account.models import EmailAddress
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import User
from catalog.models import Brand, CatalogSettings, Goods, Product
from orders.management.commands.seed_test_data import EMAIL, NAME
from orders.models import Order, PurchaseRequest


class SeedTestDataTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(DEBUG=True, MEDIA_ROOT=directory.name)
        override.enable()
        self.addCleanup(override.disable)

    def seed(self):
        output = StringIO()
        call_command("seed_test_data", stdout=output)
        return output.getvalue()

    def test_creates_complete_demo_with_regular_verified_customer(self):
        output = self.seed()
        self.assertEqual(Product.objects.count(), 6)
        self.assertEqual(Product.objects.filter(is_published=True).count(), 5)
        self.assertEqual(Goods.objects.count(), 7)
        self.assertEqual(PurchaseRequest.objects.count(), 4)
        self.assertEqual(Order.objects.count(), 3)
        customer = User.objects.get(email=EMAIL)
        self.assertFalse(customer.is_staff)
        self.assertFalse(customer.is_superuser)
        self.assertFalse(customer.groups.exists())
        self.assertTrue(EmailAddress.objects.get(user=customer).verified)
        password = output.split("Пароль: ")[1].splitlines()[0]
        self.assertTrue(customer.check_password(password))
        for product in [*Product.objects.all(), *Goods.objects.all()]:
            product.full_clean()
            self.assertEqual(product.photos.count(), 2)
            self.assertTrue(product.photos.first().image.storage.exists(product.photos.first().image.name))
        self.assertEqual(set(PurchaseRequest.objects.values_list("status", flat=True)), {"new", "in_progress", "agreed", "cancelled"})

    def test_repeat_preserves_password_manager_changes_and_existing_catalog(self):
        original = Product.objects.create(brand=Brand.objects.create(name="Original"), model="Real", powertrain="ice_4t", stock_price_rub=123456)
        config = CatalogSettings.load()
        config.stock_markup_percent = 17
        config.save()
        self.seed()
        customer = User.objects.get(email=EMAIL)
        customer.set_password("changed-demo-password-9834")
        customer.save()
        request = PurchaseRequest.objects.filter(status="new").get()
        request.status = "in_progress"
        request.manager_note = "Изменено менеджером"
        request.save()
        output = self.seed()
        self.assertEqual(Product.objects.count(), 7)
        self.assertEqual(Goods.objects.count(), 7)
        self.assertEqual(PurchaseRequest.objects.count(), 4)
        self.assertEqual(Order.objects.count(), 3)
        original.refresh_from_db()
        config.refresh_from_db()
        request.refresh_from_db()
        customer.refresh_from_db()
        self.assertEqual(original.stock_price_rub, 123456)
        self.assertEqual(config.stock_markup_percent, 17)
        self.assertEqual(request.manager_note, "Изменено менеджером")
        self.assertEqual(request.status, "in_progress")
        self.assertTrue(customer.check_password("changed-demo-password-9834"))
        self.assertNotIn("Пароль: ", output)

    @override_settings(DEBUG=False)
    def test_refuses_production(self):
        with self.assertRaises(CommandError):
            self.seed()
        self.assertFalse(User.objects.exists())
        self.assertFalse(Product.objects.exists())

    def test_refuses_conflicting_existing_account(self):
        User.objects.create_user(email=EMAIL, full_name="Другой клиент")
        with self.assertRaises(CommandError):
            self.seed()
        self.assertFalse(Product.objects.exists())
        self.assertFalse(EmailAddress.objects.exists())
