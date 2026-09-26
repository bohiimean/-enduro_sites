"""Нормализация телефона. Перенесено из бота (`bot/utils/phone.py`) с одним
добавлением: `to_e164` — тот же формат `+7XXXXXXXXXX`, который требует alfabit
(в боте эта функция жила в `handlers/payment.py` как `_to_e164`).

Формат хранения в БД — E.164 со знаком «+». В path запроса к alfabit «+» не
ставится (иначе декодируется как пробел) — об этом заботится клиент alfabit.
"""
import re


def normalize_phone(raw: str) -> str:
    """Только цифры, российский номер приводится к виду 7XXXXXXXXXX."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits
    elif digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return digits


def to_e164(raw: str) -> str | None:
    """`+7XXXXXXXXXX` или None, если на российский номер не похоже."""
    digits = normalize_phone(raw)
    if len(digits) == 11 and digits.startswith("7"):
        return "+" + digits
    return None
