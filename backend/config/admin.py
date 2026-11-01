"""Оформление SKL MOTO и меню по рабочим задачам менеджера."""
from django.urls import reverse_lazy

# Меню строится из зарегистрированных моделей и учитывает права Django Admin.
# Новые служебные модели доступны через «Все приложения».
NAVIGATION = (
    ("Каталог", (
        ("Байки", "two_wheeler", "catalog.product"),
        ("Другие товары", "inventory_2", "catalog.goods"),
        ("Категории товаров", "category", "catalog.goodscategory"),
        ("Марки", "sell", "catalog.brand"),
    )),
    ("Заказы", (
        ("Заказы и поставки", "local_shipping", "orders.order"),
        ("Номера для заказов", "contact_phone", "orders.orderphone"),
        ("Статусы поставки", "checklist", "orders.supplystatus"),
    )),
    ("Платежи", (
        ("Платежи и выдача юаня", "payments", "payments.payment"),
        ("Плательщики и KYC", "verified_user", "payments.payer"),
        ("Документы KYC", "description", "payments.kycdocument"),
    )),
    ("Курсы", (
        ("Способы оплаты", "currency_exchange", "pricing.paymentmethod"),
        ("Наценки", "percent", "pricing.markuprule"),
        ("Источники курса", "cloud_sync", "pricing.ratesource"),
        ("История котировок", "history", "pricing.ratequote"),
    )),
    ("Настройки", (
        ("Настройки каталога", "tune", "catalog.catalogsettings"),
        ("Настройки курса", "settings", "pricing.pricingsettings"),
        ("Пользователи", "group", "accounts.user"),
        ("Номера телефонов", "phone", "accounts.phonenumber"),
        ("Почтовые адреса", "mail", "account.emailaddress"),
        ("Группы и права", "admin_panel_settings", "auth.group"),
    )),
)


def navigation(request):
    from django.contrib import admin

    registered = {model._meta.label_lower: model_admin for model, model_admin in admin.site._registry.items()}
    groups = []
    for title, entries in NAVIGATION:
        items = []
        for label, icon, model_label in entries:
            model_admin = registered.get(model_label)
            if model_admin is None or not model_admin.has_module_permission(request):
                continue
            if not model_admin.has_view_or_change_permission(request):
                continue
            app, model = model_label.split(".")
            items.append({"title": label, "icon": icon, "link": reverse_lazy(f"admin:{app}_{model}_changelist")})
        if items:
            groups.append({"title": title, "separator": True, "collapsible": True, "items": items})
    return groups


UNFOLD = {
    "SITE_TITLE": "SKL MOTO — управление",
    "SITE_HEADER": "SKL MOTO",
    "SITE_SUBHEADER": "Панель управления",
    "SITE_SYMBOL": "two_wheeler",
    "SITE_URL": "/",
    "THEME": "light",
    "SHOW_BACK_BUTTON": True,
    "BORDER_RADIUS": "8px",
    "COLORS": {"primary": {
        "50": "#fff7ed", "100": "#ffedd5", "200": "#fed7aa",
        "300": "#fdba74", "400": "#fb923c", "500": "#f97316",
        "600": "#ea580c", "700": "#c2410c", "800": "#9a3412",
        "900": "#7c2d12", "950": "#431407",
    }},
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": navigation,
    },
}
