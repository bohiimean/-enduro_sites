"""Общее: нормализация телефона и «API закрыто по умолчанию»."""
from django.test import Client, SimpleTestCase, TestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.permissions import AllowAny

from .phone import normalize_phone, to_e164

# Всё, что под /api/ отвечает без входа. Новый публичный эндпоинт добавляется
# сюда осознанно, вместе с кодом — иначе тест упадёт.
PUBLIC_API = {"health", "pricing", "product-list", "product-detail"}


class PhoneNormalizationTests(SimpleTestCase):
    def test_any_russian_spelling_becomes_e164(self):
        for raw in [
            "+79123456789",
            "+7 (912) 345-67-89",
            "8 912 345 67 89",
            "89123456789",
            "9123456789",
            "7-912-345-67-89",
            " +7 912 345 6789 ",
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(to_e164(raw), "+79123456789")

    def test_not_a_russian_number(self):
        for raw in ["", None, "12345", "+1 202 555 0100", "+380 44 123 45 67", "+7 912 345 67 890"]:
            with self.subTest(raw=raw):
                self.assertIsNone(to_e164(raw))

    def test_normalize_keeps_only_digits(self):
        # Такой вид уходит в path запроса к alfabit: «+» там декодируется как
        # пробел.
        self.assertEqual(normalize_phone("+7 (912) 345-67-89"), "79123456789")


def _api_views(patterns=None, prefix=""):
    """Все именованные маршруты под api/ вместе с их view."""
    for p in get_resolver().url_patterns if patterns is None else patterns:
        route = prefix + str(p.pattern)
        if isinstance(p, URLResolver):
            yield from _api_views(p.url_patterns, route)
        elif isinstance(p, URLPattern) and route.startswith("api/"):
            yield p.name, p.callback


def _is_public(view) -> bool:
    cls = getattr(view, "cls", None)
    if cls is None:
        # Обычная Django-view: DRF её не охраняет, значит открыта.
        return True
    perms = cls.permission_classes
    return not perms or any(issubclass(p, AllowAny) for p in perms)


class ApiClosedByDefaultTests(TestCase):
    """Самая тихая ошибка проекта: забытый `AllowAny` делает приватный
    эндпоинт публичным, и снаружи это никак не видно."""

    def test_only_whitelisted_endpoints_are_public(self):
        views = list(_api_views())
        self.assertTrue(views)
        public = {name for name, view in views if _is_public(view)}

        self.assertEqual(public, PUBLIC_API)

    def test_every_api_route_has_a_name(self):
        """Без имени маршрут не попадёт в проверку выше."""
        self.assertNotIn(None, [name for name, _ in _api_views()])

    def test_private_endpoints_refuse_anonymous(self):
        client = Client()
        for path in ["/api/v1/account/me/", "/api/v1/account/phones/", "/api/v1/account/phones/1/"]:
            with self.subTest(path=path):
                self.assertIn(client.get(path).status_code, (401, 403))

    def test_public_endpoints_answer_anonymous(self):
        client = Client()
        for path in ["/api/v1/health/", "/api/v1/pricing/", "/api/v1/catalog/products/"]:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200)
