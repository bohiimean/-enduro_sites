from decimal import Decimal

from django.db import migrations


def use_rapira(apps, schema_editor):
    alias = schema_editor.connection.alias
    sources = apps.get_model("pricing", "RateSource").objects.using(alias)
    methods = apps.get_model("pricing", "PaymentMethod").objects.using(alias)
    rules = apps.get_model("pricing", "MarkupRule").objects.using(alias)
    sources.filter(code="investing").update(is_active=False)
    cash = methods.filter(code="cash_moscow").first()
    if cash is not None:
        rapira, _ = sources.get_or_create(code="rapira", defaults={"title": "Rapira USDT/RUB"})
        methods.filter(pk=cash.pk).update(source=rapira)
        # Старые уровни USD/RUB сохраняем выключенными, не применяем к USDT/RUB.
        rules.filter(method=cash).update(is_active=False)
        base = rules.filter(method=cash, label="Стандарт", weekdays="").first()
        values = dict(kind="rub_add", value=Decimal("1.15"), threshold_rub=None,
                      time_from=None, time_to=None, sort=10, is_active=True)
        if base is None:
            rules.create(method=cash, label="Стандарт", weekdays="", **values)
        else:
            rules.filter(pk=base.pk).update(**values)


class Migration(migrations.Migration):
    dependencies = [("pricing", "0002_disable_alfabit")]
    operations = [migrations.RunPython(use_rapira, migrations.RunPython.noop)]
