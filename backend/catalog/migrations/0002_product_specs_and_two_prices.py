"""Карточка байка с характеристиками и двумя ценами; мастер — админка.

Реальных данных в каталоге не было — только демо-байк из `seed_demo`, — поэтому
«в наличии» флажком не переносится в количество, а поля импорта из Sheets
просто удаляются. Цвет и цена переименованы, чтобы не терять их.
"""
import decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

NON_NEGATIVE = [django.core.validators.MinValueValidator(decimal.Decimal("0"))]


def decimal_field(verbose_name, max_digits, decimal_places, help_text=""):
    return models.DecimalField(
        blank=True, null=True, decimal_places=decimal_places, max_digits=max_digits,
        validators=NON_NEGATIVE, verbose_name=verbose_name, help_text=help_text,
    )


def small_int(verbose_name):
    return models.PositiveSmallIntegerField(blank=True, null=True, verbose_name=verbose_name)


def text(verbose_name, max_length, help_text=""):
    return models.CharField(blank=True, max_length=max_length, verbose_name=verbose_name,
                            help_text=help_text)


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
        ("pricing", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(model_name="product", name="catalog_pro_is_publ_7e3f92_idx"),
        migrations.RemoveField(model_name="product", name="in_stock"),
        migrations.RemoveField(model_name="product", name="external_key"),
        migrations.RemoveField(model_name="productphoto", name="source_url"),

        migrations.RenameField(model_name="product", old_name="color", new_name="colors"),
        migrations.AlterField(
            model_name="product", name="colors",
            field=text("цвета", 200, "Через запятую: «чёрный, белый»."),
        ),
        migrations.RenameField(model_name="product", old_name="price", new_name="stock_price_rub"),
        migrations.AlterField(
            model_name="product", name="stock_price_rub",
            field=decimal_field(
                "цена в наличии вручную, ₽", 12, 2,
                "Пусто — считается от юаней с наценкой «в наличии». "
                "Вписанную цену курс не трогает.",
            ),
        ),
        migrations.AlterField(
            model_name="product", name="model",
            field=models.CharField(
                help_text="Без года: «Ultra Bee», «G9 Pro», «Z300 S7».", max_length=150,
                verbose_name="модель",
            ),
        ),

        # Основное
        migrations.AddField(
            model_name="product", name="model_year",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name="год",
                validators=[django.core.validators.MinValueValidator(1990)],
            ),
        ),
        migrations.AddField(
            model_name="product", name="powertrain",
            field=models.CharField(
                choices=[("ice_4t", "ДВС, 4-тактный"), ("ice_2t", "ДВС, 2-тактный"),
                         ("electric", "Электро")],
                default="ice_4t", max_length=16, verbose_name="тип",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="product", name="tagline",
            field=text("коротко", 160, "Одна строка под названием в списке."),
        ),
        migrations.AddField(
            model_name="product", name="documents",
            field=models.CharField(
                blank=True, max_length=8, verbose_name="документы",
                choices=[("epts", "ЭПТС — можно поставить на учёт"),
                         ("none", "Без ПТС — для бездорожья и спорта")],
            ),
        ),

        # Цена и наличие
        migrations.AddField(
            model_name="product", name="price_cny",
            field=decimal_field(
                "цена завода, ¥", 12, 2,
                "От неё по курсу считаются обе цены. Пусто — на сайте «цена по запросу».",
            ),
        ),
        migrations.AddField(
            model_name="product", name="delivery_rub",
            field=decimal_field(
                "доставка до Москвы, ₽", 12, 2,
                "Пусто — общая из настроек каталога. 0 — доставка уже в цене завода.",
            ),
        ),
        migrations.AddField(
            model_name="product", name="stock_qty",
            field=models.PositiveIntegerField(default=0, verbose_name="в наличии в Москве, шт"),
        ),
        migrations.AddField(
            model_name="product", name="is_orderable",
            field=models.BooleanField(default=True, verbose_name="принимаем предзаказ"),
        ),
        migrations.AddField(
            model_name="product", name="lead_time",
            field=text("срок поставки", 60, "Пусто — общий из настроек каталога."),
        ),

        # Характеристики: общие
        migrations.AddField(
            model_name="product", name="engine",
            field=text("двигатель / мотор", 120, "«Zongshen NC300S», «PMSM, средний привод»."),
        ),
        migrations.AddField(
            model_name="product", name="power_hp", field=decimal_field("мощность, л.с.", 5, 1),
        ),
        migrations.AddField(
            model_name="product", name="power_kw",
            field=decimal_field("мощность, кВт", 5, 1, "У электро — пиковая."),
        ),
        migrations.AddField(
            model_name="product", name="torque_nm", field=small_int("крутящий момент, Н·м"),
        ),
        migrations.AddField(
            model_name="product", name="max_speed_kmh", field=small_int("макс. скорость, км/ч"),
        ),
        migrations.AddField(
            model_name="product", name="weight_kg",
            field=decimal_field("вес, кг", 5, 1, "Как в спецификации завода, обычно сухой."),
        ),
        migrations.AddField(
            model_name="product", name="seat_height_mm", field=small_int("высота по седлу, мм"),
        ),
        migrations.AddField(
            model_name="product", name="ground_clearance_mm", field=small_int("клиренс, мм"),
        ),
        migrations.AddField(model_name="product", name="frame", field=text("рама", 120)),
        migrations.AddField(model_name="product", name="fork", field=text("вилка", 120)),
        migrations.AddField(model_name="product", name="shock", field=text("амортизатор", 120)),
        migrations.AddField(model_name="product", name="brakes", field=text("тормоза", 120)),
        migrations.AddField(
            model_name="product", name="wheels", field=text("колёса", 60, "«21/18»."),
        ),

        # Только ДВС
        migrations.AddField(
            model_name="product", name="displacement_cc", field=small_int("объём, см³"),
        ),
        migrations.AddField(
            model_name="product", name="cooling",
            field=models.CharField(
                blank=True, max_length=8, verbose_name="охлаждение",
                choices=[("liquid", "жидкостное"), ("air", "воздушное"),
                         ("oil_air", "масляно-воздушное")],
            ),
        ),
        migrations.AddField(
            model_name="product", name="fuel_system",
            field=text("питание", 80, "«карбюратор Keihin PWK 38», «инжектор»."),
        ),
        migrations.AddField(
            model_name="product", name="transmission", field=text("КПП", 80, "«6-ступенчатая»."),
        ),
        migrations.AddField(
            model_name="product", name="starter",
            field=models.CharField(
                blank=True, max_length=8, verbose_name="запуск",
                choices=[("electric", "электростартер"), ("kick", "кикстартер"),
                         ("both", "электростартер и кик")],
            ),
        ),
        migrations.AddField(
            model_name="product", name="fuel_tank_l", field=decimal_field("бак, л", 4, 1),
        ),

        # Только электро
        migrations.AddField(
            model_name="product", name="battery_voltage_v", field=small_int("батарея, В"),
        ),
        migrations.AddField(
            model_name="product", name="battery_capacity_ah",
            field=decimal_field("батарея, А·ч", 5, 1),
        ),
        migrations.AddField(
            model_name="product", name="range_km", field=small_int("запас хода, км"),
        ),
        migrations.AddField(
            model_name="product", name="charge_time_h", field=decimal_field("зарядка, ч", 4, 1),
        ),

        migrations.CreateModel(
            name="ProductSpec",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False,
                                           verbose_name="ID")),
                ("name", models.CharField(max_length=80, verbose_name="параметр")),
                ("value", models.CharField(max_length=200, verbose_name="значение")),
                ("sort", models.PositiveIntegerField(default=0, verbose_name="порядок")),
                ("product", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="extra_specs",
                    to="catalog.product", verbose_name="байк",
                )),
            ],
            options={
                "verbose_name": "доп. характеристика",
                "verbose_name_plural": "доп. характеристики",
                "ordering": ["sort", "id"],
            },
        ),
        migrations.CreateModel(
            name="CatalogSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False,
                                           verbose_name="ID")),
                ("order_markup_percent", models.DecimalField(
                    decimal_places=2, default=decimal.Decimal("5"), max_digits=5,
                    validators=NON_NEGATIVE, verbose_name="наценка под заказ, %",
                )),
                ("stock_markup_percent", models.DecimalField(
                    decimal_places=2, default=decimal.Decimal("10"), max_digits=5,
                    validators=NON_NEGATIVE, verbose_name="наценка в наличии, %",
                )),
                ("delivery_rub", models.DecimalField(
                    decimal_places=2, default=decimal.Decimal("0"), max_digits=12,
                    validators=NON_NEGATIVE, verbose_name="доставка до Москвы, ₽",
                    help_text="Для моделей, у которых своя не указана.",
                )),
                ("lead_time", models.CharField(
                    blank=True, max_length=60, verbose_name="срок поставки под заказ",
                    help_text="Для моделей, у которых свой не указан: «45–60 дней».",
                )),
                ("round_to_rub", models.PositiveIntegerField(
                    default=1000, validators=[django.core.validators.MinValueValidator(1)],
                    verbose_name="округлять вверх до, ₽",
                )),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="изменено")),
                ("rate_method", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to="pricing.paymentmethod",
                    verbose_name="курс юаня — как у способа оплаты",
                    help_text="Берётся цена юаня этого способа со страницы курса, уровень без "
                              "порога суммы. Пусто или способ выключен на витрине — цены от "
                              "юаней не считаются.",
                )),
            ],
            options={
                "verbose_name": "настройки каталога",
                "verbose_name_plural": "настройки каталога",
            },
        ),
    ]
