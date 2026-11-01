"""Совместимость Unfold с формами, правами и каталогом проекта."""
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase
from unfold.admin import ModelAdmin

from accounts.models import User
from catalog.models import Brand, Goods, GoodsSpec, Product
from config.admin import navigation


class AdminThemeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_superuser(
            email="theme-admin@example.com", password="test-admin-password",
        )
        cls.brand = Brand.objects.create(name="Test")
        cls.product = Product.objects.create(brand=cls.brand, model="Electric", powertrain="electric")
        cls.goods = Goods.objects.create(title="Battery")

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_all_registered_models_use_unfold(self):
        for model_admin in admin.site._registry.values():
            self.assertIsInstance(model_admin, ModelAdmin)

    def test_all_registered_lists_open(self):
        for model in admin.site._registry:
            with self.subTest(model=model._meta.label):
                self.assertEqual(self.client.get(
                    f"/admin/{model._meta.app_label}/{model._meta.model_name}/",
                ).status_code, 200)

    def test_product_tabs_conditions_and_sorting_present(self):
        response = self.client.get(f"/admin/catalog/product/{self.product.pk}/change/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Двигатель и батарея")
        self.assertContains(response, "activeFieldsetTab")
        self.assertContains(response, "powertrain === &#x27;electric&#x27;", html=False)
        self.assertContains(response, 'name="photos-0-sort"')
        self.assertContains(response, 'name="extra_specs-0-sort"')

    def test_custom_user_forms_open(self):
        for url in ("/admin/accounts/user/add/",
                    f"/admin/accounts/user/{self.admin_user.pk}/change/",
                    f"/admin/accounts/user/{self.admin_user.pk}/password/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_creates_email_user(self):
        response = self.client.post("/admin/accounts/user/add/", {
            "email": "new-user@example.com", "password1": "a-long-test-password-9834",
            "password2": "a-long-test-password-9834", "usable_password": "true",
            "phones-TOTAL_FORMS": "0", "phones-INITIAL_FORMS": "0",
        })
        self.assertEqual(response.status_code, 302, response.context["adminform"].form.errors if response.context else "")
        self.assertTrue(User.objects.get(email="new-user@example.com").check_password("a-long-test-password-9834"))

    def test_navigation_only_shows_accessible_models(self):
        staff = User.objects.create_user(email="catalog-only@example.com", password="test-password", is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename="view_goods", content_type__app_label="catalog"))
        request = RequestFactory().get("/admin/")
        request.user = staff
        groups = navigation(request)
        self.assertEqual([group["title"] for group in groups], ["Каталог"])
        self.assertEqual([item["title"] for item in groups[0]["items"]], ["Другие товары"])
        self.client.force_login(staff)
        self.assertEqual(self.client.get("/admin/catalog/goods/").status_code, 200)
        self.assertEqual(self.client.post(f"/admin/catalog/goods/{self.goods.pk}/change/", {"title": "changed"}).status_code, 403)
        self.goods.refresh_from_db()
        self.assertEqual(self.goods.title, "Battery")

    def test_inline_order_saved_and_used_by_public_api(self):
        first = GoodsSpec.objects.create(product=self.goods, name="Weight", value="100 kg", sort=0)
        second = GoodsSpec.objects.create(product=self.goods, name="Energy", value="10 kWh", sort=1)
        response = self.client.post(f"/admin/catalog/goods/{self.goods.pk}/change/", {
            "title": "Battery", "availability": "order", "sort": "0", "is_published": "on",
            "photos-TOTAL_FORMS": "0", "photos-INITIAL_FORMS": "0",
            "specs-TOTAL_FORMS": "2", "specs-INITIAL_FORMS": "2",
            "specs-0-id": first.pk, "specs-0-name": "Weight", "specs-0-value": "100 kg", "specs-0-sort": "1",
            "specs-1-id": second.pk, "specs-1-name": "Energy", "specs-1-value": "10 kWh", "specs-1-sort": "0",
        })
        self.assertEqual(response.status_code, 302)
        data = self.client.get(f"/api/v1/catalog/goods/{self.goods.slug}/").json()
        self.assertEqual([item["label"] for item in data["specs"][0]["items"]], ["Energy", "Weight"])
