"""Корзина → заявка: снимок, идемпотентность, права клиента и менеджера."""
import uuid
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings

from accounts.models import User
from catalog.models import Brand, Goods, Product
from catalog.tests import make_rate
from .models import OrderPhone, PurchaseRequest

URL = "/api/v1/requests/"


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class PurchaseRequestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email="buyer@example.com", password="test-password", full_name="Иван")
        cls.other = User.objects.create_user(email="other@example.com", password="test-password")
        cls.manager = User.objects.create_superuser(email="manager@example.com", password="test-password")
        cls.bike = Product.objects.create(
            brand=Brand.objects.create(name="Test"), model="Enduro", powertrain="ice_4t",
            stock_qty=3, stock_price_rub=Decimal("250000"), price_cny=Decimal("10000"),
        )
        cls.goods = Goods.objects.create(title="Аккумулятор", price_rub=Decimal("185000.50"), availability="order", is_published=True)

    def setUp(self):
        cache.clear()
        self.client.force_login(self.user)

    def payload(self, **changes):
        data = {
            "submission_key": str(uuid.uuid4()), "name": "Иван", "phone": "8 (912) 345-67-89",
            "items": [
                {"kind": "bike", "product_id": self.bike.pk, "offer": "stock", "quantity": 2},
                {"kind": "goods", "product_id": self.goods.pk, "offer": "order", "quantity": 1},
            ],
        }
        data.update(changes)
        return data

    def post(self, data=None):
        return self.client.post(URL, data or self.payload(), content_type="application/json")

    def test_anonymous_denied(self):
        self.client.logout()
        for path in (URL, URL + "contact/", URL + "1/"):
            self.assertIn(self.client.get(path).status_code, (401, 403))
        self.assertIn(self.post().status_code, (401, 403))
        self.assertFalse(PurchaseRequest.objects.exists())

    def test_mixed_cart_and_contacts(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["phone"], "+79123456789")
        self.assertEqual(data["status"], "new")
        self.assertEqual(data["status_label"], "Ожидает обработки")
        self.assertEqual([(i["title"], i["quantity"], i["unit_price_rub"]) for i in data["items"]], [
            ("Test Enduro", 2, "250000.00"), ("Аккумулятор", 1, "185000.50"),
        ])
        self.assertEqual(PurchaseRequest.objects.get().user, self.user)
        self.assertFalse(OrderPhone.objects.exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Иван")

    def test_browser_prices_names_status_and_owner_are_ignored(self):
        data = self.payload(status="agreed", manager_note="injected", user=self.other.pk)
        data["items"][0].update(unit_price_rub="1", title="fake")
        result = self.post(data).json()
        self.assertEqual(result["status"], "new")
        self.assertEqual(result["items"][0]["unit_price_rub"], "250000.00")
        obj = PurchaseRequest.objects.get()
        self.assertEqual(obj.user, self.user)
        self.assertEqual(obj.manager_note, "")

    def test_bike_order_price_uses_catalog_formula(self):
        make_rate()
        data = self.payload(items=[{"kind": "bike", "product_id": self.bike.pk, "offer": "order", "quantity": 1}])
        self.assertEqual(self.post(data).json()["items"][0]["unit_price_rub"], "177000.00")

    def test_unknown_price_is_allowed(self):
        self.goods.price_rub = None
        self.goods.save()
        self.assertIsNone(self.post().json()["items"][1]["unit_price_rub"])

    def test_retries_return_same_request_even_after_catalog_changes(self):
        data = self.payload()
        first = self.post(data)
        self.bike.stock_qty = 0
        self.bike.save()
        self.goods.delete()
        second = self.post(data)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(PurchaseRequest.objects.count(), 1)
        self.assertEqual(PurchaseRequest.objects.get().items.count(), 2)

    def test_same_key_with_other_payload_is_conflict(self):
        data = self.payload()
        self.post(data)
        data["name"] = "Другое имя"
        self.assertEqual(self.post(data).status_code, 409)
        self.assertEqual(PurchaseRequest.objects.count(), 1)

    def test_key_is_scoped_to_account(self):
        data = self.payload()
        first = self.post(data).json()["id"]
        self.client.force_login(self.other)
        second = self.post(data).json()["id"]
        self.assertNotEqual(first, second)

    def test_snapshot_survives_rename_price_change_and_deletion(self):
        first = self.post().json()
        self.goods.title = "Новое имя"
        self.goods.price_rub = 1
        self.goods.save()
        self.bike.delete()
        self.goods.delete()
        self.assertEqual(self.client.get(URL + str(first["id"]) + "/").json(), first)

    def test_user_only_sees_own_requests_even_with_same_phone(self):
        obj = self.post().json()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(URL).json()["count"], 0)
        self.assertEqual(self.client.get(URL + str(obj["id"]) + "/").status_code, 404)
        own = self.post().json()
        self.assertEqual(self.client.get(URL).json()["count"], 1)
        self.assertEqual(self.client.get(URL).json()["results"][0]["id"], own["id"])

    def test_status_updates_and_note_remains_private(self):
        obj = self.post().json()
        PurchaseRequest.objects.filter(pk=obj["id"]).update(status="in_progress", manager_note="Служебная заметка")
        detail = self.client.get(URL + str(obj["id"]) + "/").json()
        self.assertEqual(detail["status_label"], "В работе")
        self.assertNotIn("manager_note", detail)
        self.assertNotIn("Служебная заметка", str(self.client.get(URL).json()))
        self.assertNotIn("payload_hash", detail)
        self.assertNotIn("submission_key", detail)
        for method in (self.client.patch, self.client.delete):
            self.assertEqual(method(URL + str(obj["id"]) + "/", {"status": "agreed"}, content_type="application/json").status_code, 405)

    def test_invalid_input(self):
        for changes in ({"items": []}, {"name": " "}, {"phone": "123"}, {"submission_key": "no"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.post(self.payload(**changes)).status_code, 400)
        for quantity in (0, -1, 100):
            data = self.payload()
            data["items"][0]["quantity"] = quantity
            self.assertEqual(self.post(data).status_code, 400)
        data = self.payload()
        data["items"] *= 26
        self.assertEqual(self.post(data).status_code, 400)
        self.assertFalse(PurchaseRequest.objects.exists())

    def test_duplicate_rows_rejected(self):
        data = self.payload()
        data["items"].append(data["items"][0])
        self.assertEqual(self.post(data).status_code, 400)

    def test_unavailable_item_rejects_whole_request(self):
        self.goods.is_published = False
        self.goods.save()
        self.assertEqual(self.post().status_code, 400)
        self.assertFalse(PurchaseRequest.objects.exists())
        self.goods.delete()
        self.assertEqual(self.post().status_code, 400)

    def test_changed_offer_rejected(self):
        self.goods.availability = "stock"
        self.goods.save()
        self.assertEqual(self.post().status_code, 400)
        self.assertFalse(PurchaseRequest.objects.exists())

    def test_stock_quantity_checked_without_reserving(self):
        data = self.payload()
        data["items"][0]["quantity"] = 4
        self.assertEqual(self.post(data).status_code, 400)
        self.assertEqual(self.post().status_code, 201)
        self.bike.refresh_from_db()
        self.assertEqual(self.bike.stock_qty, 3)

    def test_contacts_prefilled_only_from_own_account(self):
        self.assertEqual(self.client.get(URL + "contact/").json(), {"name": "Иван", "phone": ""})
        self.user.phones.create(phone="+79123456789")
        self.assertEqual(self.client.get(URL + "contact/").json()["phone"], "+79123456789")
        self.post(self.payload(name="Иван Петров", phone="+79991234567"))
        self.assertEqual(self.client.get(URL + "contact/").json(), {"name": "Иван Петров", "phone": "+79991234567"})

    def test_public_lookup_by_id_hides_drafts(self):
        self.assertEqual(self.client.get(f"/api/v1/catalog/products/by-id/{self.bike.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/catalog/goods/by-id/{self.goods.pk}/").status_code, 200)
        self.goods.is_published = False
        self.goods.save()
        self.assertEqual(self.client.get(f"/api/v1/catalog/goods/by-id/{self.goods.pk}/").status_code, 404)

    def test_manager_processes_request_without_editing_snapshot(self):
        obj = self.post().json()
        self.client.force_login(self.manager)
        response = self.client.get(f"/admin/orders/purchaserequest/{obj['id']}/change/")
        self.assertEqual(response.status_code, 200)
        response = self.client.post(f"/admin/orders/purchaserequest/{obj['id']}/change/", {
            "status": "agreed", "manager_note": "Связались, согласовано",
            "items-TOTAL_FORMS": "2", "items-INITIAL_FORMS": "2",
            "items-0-id": obj["items"][0]["id"], "items-1-id": obj["items"][1]["id"],
            "items-0-title": "Подмена",
        })
        self.assertEqual(response.status_code, 302)
        purchase_request = PurchaseRequest.objects.get(pk=obj["id"])
        self.assertEqual(purchase_request.status, "agreed")
        self.assertEqual(purchase_request.manager_note, "Связались, согласовано")
        self.assertEqual(purchase_request.items.first().title, "Test Enduro")


    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_registration_verification_and_csrf_protected_submission(self):
        from accounts.tests import ApiClient, AUTH, PASSWORD, last_code
        client = ApiClient()
        email = "new-cart-buyer@example.com"
        self.assertEqual(client.post_json(AUTH + "/signup", {"email": email, "password": PASSWORD}).status_code, 401)
        self.assertIn(client.post_json(URL, self.payload()).status_code, (401, 403))
        old_csrf = client.cookies["csrftoken"].value
        self.assertEqual(client.post_json(AUTH + "/email/verify", {"key": last_code(email)}).status_code, 200)
        data = self.payload()
        self.assertEqual(client.post(URL, data, content_type="application/json", HTTP_X_CSRFTOKEN=old_csrf).status_code, 403)
        result = client.post_json(URL, data)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(PurchaseRequest.objects.get().user.email, email)
        self.assertEqual(client.post_json(URL, data).json()["id"], result.json()["id"])


class ConcurrentRequestTests(TransactionTestCase):
    def test_concurrent_retries_create_one_request(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connection
        from .request_services import submit_request
        if connection.vendor != "postgresql":
            self.skipTest("Проверка блокировок PostgreSQL")
        user = User.objects.create_user(email="concurrent@example.com", password="test-password")
        goods = Goods.objects.create(title="Battery", availability="stock", is_published=True)
        data = {"submission_key": uuid.uuid4(), "name": "Иван", "phone": "+79123456789", "items": [
            {"kind": "goods", "product_id": goods.pk, "offer": "stock", "quantity": 1},
        ]}
        barrier = Barrier(2)

        def send(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                obj, created = submit_request(user, data)
                return obj.pk, created
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, range(2)))
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(PurchaseRequest.objects.count(), 1)
