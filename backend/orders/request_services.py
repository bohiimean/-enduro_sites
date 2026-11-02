"""Снимок каталога для заявки. Суммы и названия из браузера не принимаем."""
import hashlib
import json

from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from accounts.models import User
from catalog.models import CatalogSettings, Goods, Product
from catalog.pricing import current_rate, offers
from .models import PurchaseRequest, PurchaseRequestItem


class SubmissionConflict(APIException):
    status_code = 409
    default_detail = "С этой корзиной уже отправлена другая заявка. Обновите страницу и проверьте список заявок."


def snapshot_items(items):
    bikes = {p.pk: p for p in Product.objects.filter(
        pk__in=[i["product_id"] for i in items if i["kind"] == "bike"], is_published=True,
    ).select_related("brand")}
    goods = {p.pk: p for p in Goods.objects.filter(
        pk__in=[i["product_id"] for i in items if i["kind"] == "goods"], is_published=True,
    )}
    config = CatalogSettings.load() if bikes else None
    rate = current_rate(config) if config else None
    snapshots = []
    for item in items:
        product = (bikes if item["kind"] == "bike" else goods).get(item["product_id"])
        if product is None:
            raise ValidationError({"detail": "Одна из позиций больше недоступна. Удалите её из корзины и повторите отправку."})
        if item["kind"] == "bike":
            found = offers(product, config, rate)
            offer = found.stock if item["offer"] == "stock" else found.order
            available = offer is not None and (item["offer"] != "stock" or item["quantity"] <= product.stock_qty)
            price = offer.price_rub if offer else None
        else:
            available = product.availability == item["offer"]
            price = product.price_rub
        if not available:
            raise ValidationError({"detail": f"«{product.title}»: выбранное предложение или количество больше недоступно. Измените корзину."})
        snapshots.append(PurchaseRequestItem(
            kind=item["kind"], bike=product if item["kind"] == "bike" else None,
            goods=product if item["kind"] == "goods" else None, title=product.title,
            offer=item["offer"], quantity=item["quantity"], unit_price_rub=price,
        ))
    return snapshots


@transaction.atomic
def submit_request(user, data):
    # Блокировка аккаунта сериализует повторные отправки даже в разных процессах.
    User.objects.select_for_update().get(pk=user.pk)
    payload = {key: data[key] for key in ("name", "phone", "items")}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    existing = PurchaseRequest.objects.filter(user=user, submission_key=data["submission_key"]).first()
    if existing:
        if existing.payload_hash != fingerprint:
            raise SubmissionConflict()
        return existing, False
    items = snapshot_items(data["items"])
    purchase_request = PurchaseRequest.objects.create(
        user=user, name=data["name"], phone=data["phone"],
        submission_key=data["submission_key"], payload_hash=fingerprint,
    )
    for item in items:
        item.request = purchase_request
    PurchaseRequestItem.objects.bulk_create(items)
    return purchase_request, True
