"""Заказы в кабинете (решено 26.10.2026).

Главное, что здесь держится:
- аккаунт видит заказы только по своему номеру для заказов и те, что менеджер
  привязал к нему, — чужих не видит;
- номер фиксируется первым вводом: следующий ввод — заявка, а не поиск,
  и заказы до одобрения менеджером остаются старыми;
- номер занимает первый аккаунт, в любом написании;
- служебное (комментарий менеджера, ключ импорта) наружу не уходит.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase

from accounts.models import User

from .models import Order, OrderPhone, SupplyStatus

ORDERS = "/api/v1/orders/"
PHONE_URL = "/api/v1/orders/phone/"
ALICE = "+79123456789"
BOB = "+79001112233"


class OrdersTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice@example.com", "x")
        self.bob = User.objects.create_user("bob@example.com", "x")
        self.on_way = SupplyStatus.objects.create(name="В пути", sort=1)
        self.done = SupplyStatus.objects.create(name="Выдан", sort=2, is_final=True)

    def as_user(self, user) -> Client:
        client = Client()
        client.force_login(user)
        return client

    def order(self, phone=ALICE, **fields) -> Order:
        defaults = {"product_title": "Surron Ultra Bee", "price": Decimal("300000"),
                    "paid": Decimal("100000")}
        return Order.objects.create(phone=phone, **{**defaults, **fields})

    def set_phone(self, client, phone):
        return client.post(PHONE_URL, {"phone": phone}, content_type="application/json")

    def titles(self, client) -> list[str]:
        response = client.get(ORDERS)
        self.assertEqual(response.status_code, 200, response.content)
        return sorted(o["title"] for o in response.json())


class AccessTests(OrdersTestCase):
    def test_anonymous_gets_nothing(self):
        self.order()
        for path in (ORDERS, PHONE_URL):
            with self.subTest(path=path):
                self.assertIn(Client().get(path).status_code, (401, 403))
        self.assertIn(self.set_phone(Client(), ALICE).status_code, (401, 403))
        self.assertFalse(OrderPhone.objects.exists())

    def test_without_number_only_orders_linked_by_manager(self):
        self.order(product_title="по номеру")
        self.order(phone=BOB, product_title="привязан", user=self.alice)
        self.assertEqual(self.titles(self.as_user(self.alice)), ["привязан"])

    def test_own_number_shows_own_orders_only(self):
        self.order(product_title="мой")
        self.order(phone=BOB, product_title="чужой")
        self.order(phone=BOB, product_title="чужой, привязан к Бобу", user=self.bob)
        client = self.as_user(self.alice)
        self.set_phone(client, ALICE)
        self.assertEqual(self.titles(client), ["мой"])

    def test_number_and_manager_link_together(self):
        self.order(product_title="по номеру")
        self.order(phone=BOB, product_title="привязан", user=self.alice)
        client = self.as_user(self.alice)
        self.set_phone(client, ALICE)
        self.assertEqual(self.titles(client), ["по номеру", "привязан"])

    def test_newest_order_date_first_undated_last(self):
        # Заведены вперемешку, чтобы порядок создания не совпал с ожидаемым.
        self.order(product_title="октябрь", ordered_at=date(2026, 10, 3))
        self.order(product_title="без даты")
        self.order(product_title="август", ordered_at=date(2026, 8, 14))
        client = self.as_user(self.alice)
        self.set_phone(client, ALICE)
        self.assertEqual([o["title"] for o in client.get(ORDERS).json()],
                         ["октябрь", "август", "без даты"])

    def test_queries_do_not_grow_with_orders(self):
        client = self.as_user(self.alice)
        self.set_phone(client, ALICE)
        self.order(supply_status=self.on_way)
        with self.assertNumQueries(4) as one:
            client.get(ORDERS)
        for _ in range(5):
            self.order(supply_status=self.done)
        with self.assertNumQueries(len(one.captured_queries)):
            client.get(ORDERS)


class OrderFieldsTests(OrdersTestCase):
    def test_fields_like_the_bot_plus_money(self):
        self.order(
            color="синий", quantity=2, full_name="Иванов Иван", city="Казань",
            delivery_company="СДЭК", supply_status=self.done, ordered_at=date(2026, 10, 1),
            comment="звонить после 18", external_key="Лист1:42",
        )
        client = self.as_user(self.alice)
        self.set_phone(client, ALICE)
        [data] = client.get(ORDERS).json()
        self.assertEqual(data["title"], "Surron Ultra Bee")
        self.assertEqual(data["color"], "синий")
        self.assertEqual(data["quantity"], 2)
        self.assertEqual(data["full_name"], "Иванов Иван")
        self.assertEqual(data["phone"], ALICE)
        self.assertEqual(data["city"], "Казань")
        self.assertEqual(data["delivery_company"], "СДЭК")
        self.assertEqual(data["price"], "300000.00")
        self.assertEqual(data["paid"], "100000.00")
        # 300 000 − 100 000
        self.assertEqual(data["remainder"], "200000.00")
        self.assertEqual(data["status"], "Выдан")
        self.assertTrue(data["status_final"])
        self.assertEqual(data["ordered_at"], "2026-10-01")
        self.assertNotIn("comment", data)
        self.assertNotIn("external_key", data)
        self.assertNotIn("user", data)

    def test_order_without_status(self):
        self.order()
        client = self.as_user(self.alice)
        self.set_phone(client, ALICE)
        [data] = client.get(ORDERS).json()
        self.assertEqual(data["status"], "")
        self.assertFalse(data["status_final"])
        self.assertIsNone(data["ordered_at"])

    def test_title_without_product_is_dash(self):
        self.assertEqual(Order(phone=ALICE).title, "—")


class FixedNumberTests(OrdersTestCase):
    def test_no_number_yet(self):
        response = self.as_user(self.alice).get(PHONE_URL)
        self.assertEqual(response.json(), {"phone": None, "requested_phone": "", "requested_at": None})

    def test_first_entry_is_fixed_in_e164(self):
        client = self.as_user(self.alice)
        response = self.set_phone(client, "8 (912) 345-67-89")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["phone"], ALICE)
        self.assertEqual(client.get(PHONE_URL).json()["phone"], ALICE)

    def test_garbage_is_400(self):
        response = self.set_phone(self.as_user(self.alice), "12345")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(OrderPhone.objects.exists())

    def test_second_entry_is_a_request_not_a_search(self):
        self.order(product_title="мой")
        self.order(phone=BOB, product_title="чужой")
        client = self.as_user(self.alice)
        self.set_phone(client, ALICE)

        response = self.set_phone(client, BOB)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["phone"], ALICE)
        self.assertEqual(response.json()["requested_phone"], BOB)
        self.assertIsNotNone(response.json()["requested_at"])
        self.assertEqual(self.titles(client), ["мой"])

    def test_new_request_replaces_old_one(self):
        client = self.as_user(self.alice)
        self.set_phone(client, ALICE)
        self.set_phone(client, BOB)
        self.set_phone(client, "+79005556677")
        self.assertEqual(client.get(PHONE_URL).json()["requested_phone"], "+79005556677")

    def test_own_number_again_cancels_request(self):
        client = self.as_user(self.alice)
        self.set_phone(client, ALICE)
        self.set_phone(client, BOB)
        response = self.set_phone(client, "89123456789")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"phone": ALICE, "requested_phone": "", "requested_at": None})

    def test_number_taken_by_another_account_in_any_spelling(self):
        self.set_phone(self.as_user(self.bob), ALICE)
        client = self.as_user(self.alice)
        for raw in (ALICE, "8 912 345-67-89", "9123456789"):
            with self.subTest(raw=raw):
                self.assertEqual(self.set_phone(client, raw).status_code, 409)
        self.assertFalse(OrderPhone.objects.filter(user=self.alice).exists())

    def test_request_for_taken_number_is_409_and_not_saved(self):
        self.set_phone(self.as_user(self.bob), BOB)
        client = self.as_user(self.alice)
        self.set_phone(client, ALICE)
        self.assertEqual(self.set_phone(client, BOB).status_code, 409)
        self.assertEqual(client.get(PHONE_URL).json()["requested_phone"], "")

    def test_race_lost_to_another_account_is_409(self):
        # Проверка «занят ли» прошла, а запись упала на уникальности: номер
        # заняли между ними.
        client = self.as_user(self.alice)
        with mock.patch("django.db.models.query.QuerySet.create", side_effect=IntegrityError):
            response = self.set_phone(client, ALICE)
        self.assertEqual(response.status_code, 409)


class ManagerApprovalTests(OrdersTestCase):
    def setUp(self):
        super().setUp()
        self.phone = OrderPhone.objects.create(user=self.alice, phone=ALICE)

    def test_approval_switches_orders_to_new_number(self):
        self.order(product_title="старый")
        self.order(phone=BOB, product_title="новый")
        self.phone.request_change(BOB)

        self.assertTrue(self.phone.approve_change())
        self.phone.refresh_from_db()
        self.assertEqual(self.phone.phone, BOB)
        self.assertEqual(self.phone.requested_phone, "")
        self.assertIsNone(self.phone.requested_at)
        self.assertIsNotNone(self.phone.changed_at)
        self.assertEqual(self.titles(self.as_user(self.alice)), ["новый"])

    def test_nothing_to_approve(self):
        self.assertFalse(self.phone.approve_change())
        self.phone.refresh_from_db()
        self.assertEqual(self.phone.phone, ALICE)
        self.assertIsNone(self.phone.changed_at)

    def test_number_taken_while_request_waited(self):
        self.phone.request_change(BOB)
        OrderPhone.objects.create(user=self.bob, phone=BOB)
        self.assertFalse(self.phone.approve_change())
        self.phone.refresh_from_db()
        self.assertEqual(self.phone.phone, ALICE)
        self.assertEqual(self.phone.requested_phone, BOB)

    def test_reject(self):
        self.phone.request_change(BOB)
        self.assertTrue(self.phone.reject_change())
        self.phone.refresh_from_db()
        self.assertEqual((self.phone.phone, self.phone.requested_phone), (ALICE, ""))
        self.assertIsNone(self.phone.requested_at)
        self.assertFalse(self.phone.reject_change())


class AdminTests(OrdersTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser("admin@example.com", "x"))

    def test_pages_open(self):
        order = self.order()
        phone = OrderPhone.objects.create(user=self.alice, phone=ALICE)
        for path in (
            "/admin/orders/order/", "/admin/orders/order/add/",
            f"/admin/orders/order/{order.pk}/change/",
            "/admin/orders/orderphone/", f"/admin/orders/orderphone/{phone.pk}/change/",
            "/admin/orders/orderphone/?request=pending",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_order_phone_is_normalized_on_save(self):
        response = self.client.post("/admin/orders/order/add/", {
            "phone": "8 912 345 67 89", "quantity": "1", "price": "0", "paid": "0",
        })
        self.assertEqual(response.status_code, 302, response.content)
        self.assertEqual(Order.objects.get().phone, ALICE)

    def test_order_with_bad_phone_is_refused(self):
        response = self.client.post("/admin/orders/order/add/", {
            "phone": "123", "quantity": "1", "price": "0", "paid": "0",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())

    def test_order_phone_model_normalizes_both_numbers(self):
        phone = OrderPhone(user=self.alice, phone="89123456789", requested_phone="9001112233")
        phone.full_clean()
        self.assertEqual((phone.phone, phone.requested_phone), (ALICE, BOB))
        with self.assertRaises(ValidationError):
            OrderPhone(user=self.alice, phone=ALICE, requested_phone="1").full_clean()

    def test_pending_requests_are_announced(self):
        phone = OrderPhone.objects.create(user=self.alice, phone=ALICE)
        page = self.client.get("/admin/orders/orderphone/")
        self.assertNotIn("Ждут смены номера", page.content.decode())
        phone.request_change(BOB)
        page = self.client.get("/admin/orders/orderphone/")
        self.assertIn("Ждут смены номера: 1.", page.content.decode())
        filtered = self.client.get("/admin/orders/orderphone/?request=pending")
        self.assertNotIn("Ждут смены номера", filtered.content.decode())

    def test_filter_shows_only_pending(self):
        waiting = OrderPhone.objects.create(user=self.alice, phone=ALICE)
        waiting.request_change(BOB)
        OrderPhone.objects.create(user=self.bob, phone="+79005556677")
        page = self.client.get("/admin/orders/orderphone/?request=pending").content.decode()
        self.assertIn(ALICE, page)
        self.assertNotIn("+79005556677", page)

    def action(self, name, *phones):
        return self.client.post("/admin/orders/orderphone/", {
            "action": name, "_selected_action": [p.pk for p in phones],
        }, follow=True)

    def test_approve_action(self):
        waiting = OrderPhone.objects.create(user=self.alice, phone=ALICE)
        waiting.request_change(BOB)
        idle = OrderPhone.objects.create(user=self.bob, phone="+79005556677")
        response = self.action("approve_change", waiting, idle)
        texts = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertIn("Номер сменён: 1.", texts)
        self.assertTrue(any("Пропущено 1" in t for t in texts))
        waiting.refresh_from_db()
        self.assertEqual(waiting.phone, BOB)

    def test_reject_action(self):
        waiting = OrderPhone.objects.create(user=self.alice, phone=ALICE)
        waiting.request_change(BOB)
        response = self.action("reject_change", waiting)
        self.assertIn("Заявок отклонено: 1.", [str(m) for m in get_messages(response.wsgi_request)])
        waiting.refresh_from_db()
        self.assertEqual(waiting.requested_phone, "")
