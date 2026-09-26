import os
from decimal import Decimal


def _list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


TOKEN = os.environ.get("RATE_SERVICE_TOKEN", "")

SOURCE_RAPIRA = "rapira"
SOURCE_INVESTING = "investing"
SOURCE_ALFABIT = "alfabit_showcase"
ALL_SOURCES = (SOURCE_RAPIRA, SOURCE_INVESTING, SOURCE_ALFABIT)

SOURCES_ENABLED = _list("SOURCES_ENABLED", ",".join(ALL_SOURCES))
REFRESH_MINUTES = int(os.environ.get("REFRESH_MINUTES", "20"))

CHROME_BINARY_PATH = os.environ.get("CHROME_BINARY_PATH") or None
TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY") or None

ALFABIT_BASE_URL = os.environ.get("ALFABIT_BASE_URL", "https://alfabit.org")
ALFABIT_RATE_DIRECTION = os.environ.get("ALFABIT_RATE_DIRECTION", "buy")
ALFABIT_API_KEY = os.environ.get("ALFABIT_API_KEY") or None
ALFABIT_SECRET_KEY = os.environ.get("ALFABIT_SECRET_KEY") or None
# Аварийный клапан: комиссия метода оплаты, если список методов у alfabit пуст.
# По умолчанию пусто — тогда курс витрины просто не отдаётся. Не включать не
# глядя: с неверным значением цена уедет молча.
_fee_fallback = os.environ.get("ALFABIT_FEE_PERCENT_FALLBACK", "").strip()
ALFABIT_FEE_PERCENT_FALLBACK = Decimal(_fee_fallback) if _fee_fallback else None
