import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from decimal import Decimal

import aiohttp

from .base import RateProvider

logger = logging.getLogger(__name__)

_API_URL = "https://api.rapira.net/open/market/rates"
_SYMBOL = "USDT/RUB"


class RapiraProvider(RateProvider):
    """Сырая котировка USDT/RUB. Наценки здесь нет и быть не должно.

    В боте этот же провайдер умножал на 1.045. При переносе множитель вырезан:
    наценки живут в БД Django (`pricing.MarkupRule`) и правятся в админке, а
    сервис курсов отдаёт только то, что сказал источник.
    """

    def __init__(self):
        self._retry_at = 0.0

    async def get_rate(self) -> Decimal:
        if time.monotonic() < self._retry_at:
            raise RuntimeError("Rapira: пауза после ограничения API")
        async with aiohttp.ClientSession() as session:
            async with session.get(_API_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status in (429, 403):
                    # Не усиливаем блокировку повторами. Retry-After бывает
                    # числом секунд либо HTTP-датой; без него ждём 5 минут.
                    retry = resp.headers.get("Retry-After", "")
                    delay = 300.0
                    try:
                        delay = max(delay, float(retry))
                    except ValueError:
                        try:
                            delay = max(delay, (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds())
                        except (ValueError, TypeError, OverflowError):
                            pass
                    self._retry_at = time.monotonic() + delay
                resp.raise_for_status()
                data = await resp.json()

        pairs = data.get("data", [])
        pair = next((p for p in pairs if p.get("symbol") == _SYMBOL), None)
        if pair is None:
            raise ValueError(f"Pair {_SYMBOL} not found in Rapira response")

        raw = pair.get("close") or (
            (Decimal(str(pair["bidPrice"])) + Decimal(str(pair["askPrice"]))) / 2
        )
        value = Decimal(str(raw))
        if not value.is_finite() or value <= 0:
            raise ValueError("Rapira: некорректная котировка")
        return value
