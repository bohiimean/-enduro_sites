"""Произвольные товары: публикация, ручная цена, характеристики и фильтры."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Goods, GoodsCategory, GoodsPhoto, GoodsSpec


class GoodsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = GoodsCategory.objects.create(name="Энергия для дома")
        cls.battery = Goods.objects.create(
            title="Домашний аккумулятор", category=cls.category,
            price_rub=Decimal("185000.50"), availability="stock", is_published=True,
            description="Для резервного питания\nГарантия 3 года",
        )
        cls.order = Goods.objects.create(
            title="Генератор", availability="order", lead_time="30–45 дней", is_published=True,
        )
        cls.draft = Goods.objects.create(title="Черновик", category=cls.category)
        GoodsSpec.objects.create(product=cls.battery, name="Вес", value="100 кг", sort=2)
        GoodsSpec.objects.create(product=cls.battery, name="Ёмкость", value="10 кВт·ч", sort=1)
        GoodsPhoto.objects.create(product=cls.battery, image="goods/battery.jpg", sort=1)

    def test_public_list_and_detail(self):
        response = self.client.get("/api/v1/catalog/goods/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        data = self.client.get(f"/api/v1/catalog/goods/{self.battery.slug}/").json()
        self.assertEqual(data["price_rub"], "185000.50")
        self.assertEqual(data["category"]["name"], "Энергия для дома")
        self.assertEqual(data["specs"][0]["items"], [
            {"label": "Ёмкость", "value": "10 кВт·ч"},
            {"label": "Вес", "value": "100 кг"},
        ])
        self.assertEqual(data["highlights"], ["Ёмкость: 10 кВт·ч", "Вес: 100 кг"])
        self.assertEqual(data["photos"][0]["url"], "/media/goods/battery.jpg")
        self.assertNotIn("powertrain", data)
        self.assertNotIn("rate", data)

    def test_draft_and_missing_not_accessible(self):
        for slug in (self.draft.slug, "missing"):
            self.assertEqual(self.client.get(f"/api/v1/catalog/goods/{slug}/").status_code, 404)

    def test_optional_price_and_specs(self):
        data = self.client.get(f"/api/v1/catalog/goods/{self.order.slug}/").json()
        self.assertIsNone(data["price_rub"])
        self.assertEqual(data["specs"], [])
        self.assertEqual(data["photos"], [])
        self.assertIsNone(data["category"])
        self.assertEqual(data["lead_time"], "30–45 дней")

    def test_filters_and_pagination(self):
        url = "/api/v1/catalog/goods/"
        data = self.client.get(url, {"category": self.category.pk, "availability": "stock"}).json()
        self.assertEqual([p["id"] for p in data["results"]], [self.battery.pk])
        self.assertEqual(self.client.get(url, {"availability": "order"}).json()["count"], 1)
        self.assertEqual(self.client.get(url, {"limit": 1}).json()["count"], 2)
        self.assertEqual(len(self.client.get(url, {"limit": 1, "offset": 1}).json()["results"]), 1)
        for params in ({"availability": "unknown"}, {"category": "oops"}, {"category": "9" * 100}):
            self.assertEqual(self.client.get(url, params).json()["count"], 2)

    def test_categories_only_with_published_goods(self):
        GoodsCategory.objects.create(name="Пустая")
        hidden = GoodsCategory.objects.create(name="Только черновики")
        Goods.objects.create(title="Скрыт", category=hidden)
        Goods.objects.create(title="Ещё один", category=self.category, is_published=True)
        self.assertEqual(self.client.get("/api/v1/catalog/goods-categories/").json(), [
            {"id": self.category.pk, "name": self.category.name},
        ])

    def test_slug_generation_stable_and_unique_for_cyrillic(self):
        other = Goods.objects.create(title="Другой аккумулятор")
        self.assertNotEqual(other.slug, self.battery.slug)
        original = other.slug
        other.title = "Новое название"
        other.save()
        self.assertEqual(other.slug, original)

    def test_negative_price_rejected_and_zero_preserved(self):
        item = Goods(title="Товар", price_rub=Decimal("-1"))
        with self.assertRaises(ValidationError):
            item.full_clean()
        item.price_rub = Decimal("0")
        item.full_clean()
        item.is_published = True
        item.save()
        self.assertEqual(self.client.get(f"/api/v1/catalog/goods/{item.slug}/").json()["price_rub"], "0.00")

    def test_category_deletion_keeps_goods(self):
        self.category.delete()
        self.battery.refresh_from_db()
        self.assertIsNone(self.battery.category)

    def test_api_read_only(self):
        self.assertEqual(self.client.post("/api/v1/catalog/goods/", {"title": "Взлом"}).status_code, 405)

    def test_list_uses_fixed_number_of_queries(self):
        # Пагинация + товары с категорией + фото + характеристики.
        with self.assertNumQueries(4):
            self.client.get("/api/v1/catalog/goods/")


class GoodsAdminTests(TestCase):
    def setUp(self):
        from accounts.models import User
        self.client.force_login(User.objects.create_superuser(
            email="goods-admin@example.com", password="test-admin-password",
        ))

    def test_admin_saves_goods_with_free_form_specs(self):
        response = self.client.post("/admin/catalog/goods/add/", {
            "title": "Аккумулятор", "slug": "", "price_rub": "185000",
            "availability": "order", "lead_time": "30–45 дней", "sort": "0",
            "photos-TOTAL_FORMS": "0", "photos-INITIAL_FORMS": "0",
            "photos-MIN_NUM_FORMS": "0", "photos-MAX_NUM_FORMS": "1000",
            "specs-TOTAL_FORMS": "1", "specs-INITIAL_FORMS": "0",
            "specs-MIN_NUM_FORMS": "0", "specs-MAX_NUM_FORMS": "1000",
            "specs-0-name": "Ёмкость", "specs-0-value": "10 кВт·ч", "specs-0-sort": "0",
            "_save": "Сохранить",
        })
        self.assertEqual(response.status_code, 302)
        product = Goods.objects.get()
        self.assertFalse(product.is_published)
        self.assertEqual(product.price_rub, Decimal("185000"))
        self.assertEqual(product.specs.get().value, "10 кВт·ч")
