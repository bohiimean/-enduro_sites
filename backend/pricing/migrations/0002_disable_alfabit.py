from django.db import migrations


def disable_alfabit(apps, schema_editor):
    alias = schema_editor.connection.alias
    apps.get_model("pricing", "RateSource").objects.using(alias).filter(
        code="alfabit_showcase"
    ).update(is_active=False)
    methods = apps.get_model("pricing", "PaymentMethod").objects.using(alias)
    methods.filter(source__code="alfabit_showcase").update(is_active=False)
    methods.filter(code="qr_kyc").update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("pricing", "0001_initial")]
    # Не включаем автоматически то, что менеджер мог отключить до миграции.
    operations = [migrations.RunPython(disable_alfabit, migrations.RunPython.noop)]
