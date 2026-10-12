"""Характеристики байка для карточки: блоки «подпись — значение» и две-три
главные цифры для списка.

Подписи и единицы собираются здесь, а не во фронтенде: так у всех карточек
одинаковый вид, а правило «какие поля показывать этому типу» проверяется
тестами бэкенда.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .models import Product


@dataclass(frozen=True)
class SpecItem:
    label: str
    value: str


@dataclass
class SpecGroup:
    title: str
    items: list[SpecItem] = field(default_factory=list)

    def add(self, label: str, value: str | None) -> None:
        if value:
            self.items.append(SpecItem(label, value))


def fmt_number(value: Decimal | int) -> str:
    """85.0 → «85», 24.5 → «24,5», 100 → «100», а не «1E+2»."""
    return format(Decimal(value).normalize(), "f").replace(".", ",")


def _with_unit(value: Decimal | int | None, unit: str, prefix: str = "") -> str | None:
    if value is None:
        return None
    return f"{prefix}{fmt_number(value)} {unit}"


def _power(product: Product, both: bool = True) -> str | None:
    kw = _with_unit(product.power_kw, "кВт")
    hp = _with_unit(product.power_hp, "л.с.")
    # Электро меряют в киловаттах, ДВС — в лошадиных силах; вторая единица —
    # в скобках, если менеджер заполнил обе.
    main, extra = (kw, hp) if product.is_electric else (hp, kw)
    if both and main and extra:
        return f"{main} ({extra})"
    return main or extra


def _battery(product: Product, with_energy: bool = True) -> str | None:
    volts = _with_unit(product.battery_voltage_v, "В")
    amp_hours = _with_unit(product.battery_capacity_ah, "А·ч")
    text = " · ".join(part for part in (volts, amp_hours) if part)
    if not text:
        return None
    if with_energy and volts and amp_hours:
        kwh = (product.battery_voltage_v * product.battery_capacity_ah / 1000).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        text += f" ({fmt_number(kwh)} кВт·ч)"
    return text


def spec_groups(product: Product) -> list[SpecGroup]:
    if product.is_electric:
        drive = SpecGroup("Мотор и батарея")
        drive.add("Мотор", product.engine)
        drive.add("Мощность", _power(product))
        drive.add("Крутящий момент", _with_unit(product.torque_nm, "Н·м"))
        drive.add("Батарея", _battery(product))
        drive.add("Запас хода", _with_unit(product.range_km, "км", prefix="до "))
        drive.add("Зарядка", _with_unit(product.charge_time_h, "ч"))
        drive.add("Макс. скорость", _with_unit(product.max_speed_kmh, "км/ч"))
    else:
        drive = SpecGroup("Двигатель")
        drive.add("Двигатель", product.engine)
        drive.add("Тип", "2-тактный" if product.powertrain == Product.ICE_2T else "4-тактный")
        drive.add("Объём", _with_unit(product.displacement_cc, "см³"))
        drive.add("Мощность", _power(product))
        drive.add("Крутящий момент", _with_unit(product.torque_nm, "Н·м"))
        drive.add("Охлаждение", product.get_cooling_display())
        drive.add("Питание", product.fuel_system)
        drive.add("КПП", product.transmission)
        drive.add("Запуск", product.get_starter_display())
        drive.add("Бак", _with_unit(product.fuel_tank_l, "л"))
        drive.add("Макс. скорость", _with_unit(product.max_speed_kmh, "км/ч"))

    chassis = SpecGroup("Ходовая часть")
    chassis.add("Рама", product.frame)
    chassis.add("Вилка", product.fork)
    chassis.add("Амортизатор", product.shock)
    chassis.add("Тормоза", product.brakes)
    chassis.add("Колёса", product.wheels)

    size = SpecGroup("Размеры и вес")
    size.add("Вес", _with_unit(product.weight_kg, "кг"))
    size.add("Высота по седлу", _with_unit(product.seat_height_mm, "мм"))
    size.add("Клиренс", _with_unit(product.ground_clearance_mm, "мм"))

    extra = SpecGroup("Дополнительно")
    for spec in product.extra_specs.all():
        extra.add(spec.name, spec.value)

    return [group for group in (drive, chassis, size, extra) if group.items]


def highlights(product: Product) -> list[str]:
    """Две-три цифры под названием в списке: по ним байки сравнивают."""
    if product.is_electric:
        found = [
            _power(product, both=False),
            _battery(product, with_energy=False),
            _with_unit(product.range_km, "км", prefix="до "),
        ]
    else:
        found = [
            _with_unit(product.displacement_cc, "см³"),
            "2T" if product.powertrain == Product.ICE_2T else "4T",
            _power(product, both=False),
        ]
    return [item for item in found if item]
